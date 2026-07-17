import os
import subprocess
import logging
import re
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# Thư mục gốc của dự án
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_ffmpeg_path() -> str:
    """Lấy đường dẫn tới file ffmpeg.exe cục bộ trong thư mục ffmpeg của dự án, hoặc fallback."""
    local_path = os.path.join(BASE_DIR, "ffmpeg", "ffmpeg.exe")
    if os.path.exists(local_path):
        return local_path
    return "ffmpeg"

def get_ffprobe_path() -> str:
    """Lấy đường dẫn tới file ffprobe.exe cục bộ trong thư mục ffmpeg của dự án, hoặc fallback."""
    local_path = os.path.join(BASE_DIR, "ffmpeg", "ffprobe.exe")
    if os.path.exists(local_path):
        return local_path
    return "ffprobe"

def srt_time_to_seconds(time_str: str) -> float:
    """
    Chuyển đổi chuỗi thời gian SRT (HH:MM:SS,mmm hoặc HH:MM:SS.mmm) thành số giây (float).
    Ví dụ: '00:01:20,123' -> 80.123
    """
    try:
        time_str = time_str.strip().replace(',', '.')
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return float(m) * 60 + float(s)
        else:
            return float(parts[0])
    except Exception as e:
        logger.error(f"Lỗi khi parse thời gian '{time_str}': {e}")
        return 0.0

def get_video_resolution(video_path: str) -> Tuple[int, int]:
    """Lấy độ phân giải (Width, Height) của video bằng ffprobe."""
    ffprobe = get_ffprobe_path()
    cmd = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path
    ]
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            timeout=10
        )
        if result.returncode == 0:
            res_str = result.stdout.strip()
            match = re.match(r"^(\d+)x(\d+)", res_str)
            if match:
                return int(match.group(1)), int(match.group(2))
            raise RuntimeError(f"Định dạng độ phân giải không hợp lệ: {res_str}")
        else:
            raise RuntimeError(f"ffprobe thất bại: {result.stderr.strip()}")
    except Exception as e:
        logger.error(f"Lỗi khi lấy độ phân giải video {video_path}: {e}")
        # Mặc định fallback nếu lỗi
        return 1920, 1080

def get_video_duration(video_path: str) -> float:
    """Lấy tổng thời lượng (giây) của video bằng ffprobe."""
    ffprobe = get_ffprobe_path()
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            timeout=10
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Lỗi khi lấy thời lượng video {video_path}: {e}")
    return 0.0

def replace_video_segments(video_path: str, segments: List[Dict], output_path: str, log_callback=None) -> bool:
    """
    Sử dụng FFmpeg overlay để thay thế hình ảnh tại các phân đoạn chỉ định bằng ảnh tĩnh mới,
    giữ nguyên luồng âm thanh gốc của video mà không làm mất đồng bộ.
    
    `segments` có định dạng: [{"start_sec": 10.5, "end_sec": 15.0, "image_path": "path/to/img.png"}]
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            logger.info(msg)

    if not segments:
        log("⚠️ Không có phân đoạn nào cần thay thế. Sao chép trực tiếp video gốc...")
        import shutil
        try:
            shutil.copy2(video_path, output_path)
            return True
        except Exception as e:
            log(f"❌ Không thể sao chép video gốc: {e}")
            return False

    video_duration = get_video_duration(video_path)
    log(f"📹 Thời lượng video gốc: {video_duration:.2f} giây")

    # Lọc và giới hạn các phân đoạn nằm trong phạm vi thời lượng thực tế của video gốc
    valid_segments = []
    for idx, seg in enumerate(segments):
        start = seg["start_sec"]
        if video_duration > 0 and start >= video_duration:
            log(f"⚠️ Bỏ qua phân đoạn {idx+1} bắt đầu lúc {start:.2f}s vì vượt quá thời lượng video ({video_duration:.2f}s)")
            continue
            
        end = start + 5.0 # Mặc định hiển thị cố định 5.0 giây
        if video_duration > 0 and end > video_duration:
            log(f"✂️ Giới hạn thời gian kết thúc phân đoạn {idx+1} từ {end:.2f}s về {video_duration:.2f}s")
            end = video_duration
            
        if end - start <= 0:
            continue
            
        seg["end_sec"] = end
        valid_segments.append(seg)
        
    segments = valid_segments
    if not segments:
        log("⚠️ Không có phân đoạn hợp lệ nào sau khi lọc theo thời lượng video. Sao chép video gốc...")
        import shutil
        try:
            shutil.copy2(video_path, output_path)
            return True
        except Exception as e:
            log(f"❌ Không thể sao chép video gốc: {e}")
            return False

    ffmpeg = get_ffmpeg_path()
    
    # Lấy kích thước video gốc để scale ảnh vừa vặn
    W, H = get_video_resolution(video_path)
    log(f"📹 Độ phân giải video gốc: {W}x{H}")

    # Xây dựng lệnh FFmpeg
    cmd = [
        ffmpeg,
        "-i", video_path
    ]
    
    # Thêm các tệp hình ảnh đầu vào (mặc định luôn hiển thị 5.0 giây)
    for seg in segments:
        duration = 5.0
        cmd.extend(["-loop", "1", "-t", f"{duration:.3f}", "-i", seg["image_path"]])

    # Bước 1: Khởi tạo luồng ảnh tĩnh (Scale & Pad khớp video gốc) và mờ dần (Fade)
    filter_parts = []
    
    for idx, seg in enumerate(segments):
        img_idx = idx + 1
        start = seg["start_sec"]
        end = seg["end_sec"]
        duration = end - start
        
        # 1. Scale và pad ảnh tĩnh về đúng độ phân giải video gốc mà không làm méo tỉ lệ ảnh (không rung lắc, giữ độ nét gốc)
        scale_filter = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"
            
        # Dịch chuyển PTS để khớp với timeline của video gốc
        pts_filter = f"setpts=PTS+{start}/TB"
        
        # 2. Thêm hiệu ứng chuyển cảnh mờ dần (fade-in / fade-out)
        fade_duration = min(0.5, duration / 2.0)
        fade_filter = f"format=yuva420p,fade=t=in:st={start}:d={fade_duration}:alpha=1,fade=t=out:st={end-fade_duration}:d={fade_duration}:alpha=1"
        
        filter_parts.append(f"[{img_idx}:v]{scale_filter},{pts_filter},{fade_filter}[scaled_img{img_idx}]")

    # Bước 2: Chuỗi các bộ lọc overlay
    last_v = "0:v"
    for idx, seg in enumerate(segments):
        img_idx = idx + 1
        out_v = f"v{img_idx}" if idx < len(segments) - 1 else "outv"
        
        start = seg["start_sec"]
        end = seg["end_sec"]
        
        # overlays đè ảnh lên video trong khoảng thời gian [start, end] (eof_action=pass để tự động chuyển tiếp luồng chính mượt mà khi ảnh phụ hết)
        filter_parts.append(
            f"[{last_v}][scaled_img{img_idx}]overlay=x=0:y=0:enable='between(t,{start:.3f},{end:.3f})':eof_action=pass[{out_v}]"
        )
        last_v = out_v

    filter_complex_str = ";".join(filter_parts)
    
    cmd.extend([
        "-filter_complex", filter_complex_str,
        "-map", "[outv]",
        "-map", "0:a?", # Map audio stream nếu có, bỏ qua nếu video không có âm thanh
        "-c:a", "copy",   # Sao chép trực tiếp audio stream (không re-encode)
        "-c:v", "libx264",# Re-encode video stream sang h264
        "-preset", "medium",
        "-crf", "23",
        "-y",
        output_path
    ])

    log(f"🎬 Khởi chạy FFmpeg xử lý ghép đè hình ảnh...")
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Đọc stderr để hiển thị log tiến độ (FFmpeg in log ra stderr)
        while True:
            line = process.stderr.readline()
            if not line:
                break
            line_str = line.strip()
            # Lọc log FFmpeg để hiển thị các thông tin tiến độ chính cho người dùng
            if "frame=" in line_str or "size=" in line_str:
                log(f"   ⏳ {line_str}")
        
        process.wait()
        
        if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            log(f"✅ Xử lý video thành công! Đầu ra lưu tại: {output_path}")
            return True
        else:
            error_msg = process.stderr.read().strip()
            log(f"❌ FFmpeg xử lý thất bại (Code {process.returncode}): {error_msg}")
            return False
            
    except Exception as e:
        log(f"❌ Ngoại lệ xảy ra trong FFmpeg: {e}")
        return False

def format_time(seconds: float) -> str:
    """Chuyển đổi giây sang định dạng thời gian SRT: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
        if s == 60:
            m += 1
            s = 0
            if m == 60:
                h += 1
                m = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def transcribe_video_to_srt(video_path: str, output_srt_path: str, model_name: str = "base", log_callback=None) -> bool:
    """
    Sử dụng OpenAI Whisper trích xuất giọng nói từ video thành file phụ đề SRT.
    Model mặc định là 'base' để tăng độ chuẩn xác tiếng Việt và vẫn chạy nhanh, nhẹ.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            logger.info(msg)

    try:
        import whisper
        
        # Tự động tạo thư mục chứa model cục bộ ngay trong thư mục dự án
        base_dir = os.path.dirname(os.path.abspath(__file__))
        local_model_dir = os.path.join(base_dir, "whisper_models")
        os.makedirs(local_model_dir, exist_ok=True)
        
        local_model_path = os.path.join(local_model_dir, f"{model_name}.pt")
        
        # Nếu có file model cục bộ (được tải sẵn hoặc đi kèm khi đóng gói)
        if os.path.exists(local_model_path):
            log(f"🎙️ Phát hiện file mô hình cục bộ tại: {local_model_path}. Tiến hành tải offline...")
            model = whisper.load_model(local_model_path)
        else:
            log(f"🎙️ Không thấy file mô hình cục bộ. Đang tải mô hình '{model_name}' từ Internet (khoảng 140MB, chỉ tải 1 lần đầu)...")
            model = whisper.load_model(model_name, download_root=local_model_dir)
            log(f"💾 Đã lưu mô hình thành công tại: {local_model_dir}")
        log("🎙️ Đang phân tích âm thanh từ video để tự động nhận diện ngôn ngữ và sinh phụ đề...")
        # Tiến hành transcribe tự động nhận diện ngôn ngữ (hỗ trợ tiếng Việt, Anh, Tây Ban Nha,...)
        result = model.transcribe(video_path, verbose=False)
        
        log(f"💾 Đang ghi phụ đề ra file: {output_srt_path}")
        with open(output_srt_path, "w", encoding="utf-8") as f:
            for idx, seg in enumerate(result.get("segments", []), 1):
                start = seg.get("start", 0.0)
                end = seg.get("end", 0.0)
                text = seg.get("text", "").strip()
                
                # Định dạng chuẩn SRT
                f.write(f"{idx}\n")
                f.write(f"{format_time(start)} --> {format_time(end)}\n")
                f.write(f"{text}\n\n")
                
        log("✅ Trích xuất phụ đề tự động thành công!")
        return True
    except Exception as e:
        import traceback
        err_msg = f"❌ Lỗi trích xuất phụ đề: {e}\n{traceback.format_exc()}"
        log(err_msg)
        logger.error(err_msg)
        return False

