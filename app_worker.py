import os
import shutil
import logging
import json
import traceback
import base64
import time
from PySide6.QtCore import QThread, Signal
from browser_controller import BrowserAutomationController
from video_processor import replace_video_segments, srt_time_to_seconds

logger = logging.getLogger(__name__)

# Thư mục gốc của dự án
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GOOGLE_PROFILE_PATH = os.path.join(BASE_DIR, "profiles", "google_profile")

class AppWorker(QThread):
    """
    Worker xử lý chạy nền quy trình: Phân tích SRT -> Tạo ảnh AI -> Overlay bằng FFmpeg.
    Giúp giao diện người dùng PySide6 luôn mượt mà.
    """
    progress_updated = Signal(int)       # Tiến trình (%)
    status_updated = Signal(str)        # Trạng thái hiện tại
    log_message = Signal(str)           # Nội dung log thời gian thực
    finished = Signal(str)              # Hoàn thành, truyền đường dẫn video đầu ra
    error_occurred = Signal(str)        # Lỗi xảy ra
    user_decision_requested = Signal(list) # Yêu cầu người dùng lựa chọn khi lỗi ảnh

    def __init__(self, video_path: str, srt_path: str, n_keywords: int, output_dir: str, image_model: str = 'GEM_PIX_2', aspect_ratio: str = '16:9', custom_prompt: str = "", headless: bool = True, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.srt_path = srt_path
        self.n_keywords = n_keywords
        self.output_dir = output_dir
        self.image_model = image_model
        self.aspect_ratio = aspect_ratio
        self.custom_prompt = custom_prompt
        self.headless = headless
        self.controller = None
        self._is_stopped = False
        self.user_decision = None

    def stop(self):
        """Dừng khẩn cấp tiến trình."""
        self._is_stopped = True
        self.log("⚠️ Nhận tín hiệu yêu cầu dừng từ người dùng. Đang dọn dẹp...")
        if self.controller:
            try:
                self.controller.cleanup()
            except Exception:
                pass

    def log(self, msg: str):
        """Gửi log hiển thị ra UI."""
        self.log_message.emit(msg)

    def run(self):
        temp_dir = os.path.join(BASE_DIR, "temp_images")
        
        try:
            self.log("🚀 Bắt đầu quy trình xử lý Video Visual Replacer...")
            self.progress_updated.emit(2)
            
            # --- KIỂM TRA ĐẦU VÀO ---
            self.status_updated.emit("Kiểm tra tệp tin đầu vào...")
            if not os.path.exists(self.video_path):
                raise FileNotFoundError(f"Không tìm thấy tệp video: {self.video_path}")
            if not os.path.exists(self.srt_path):
                raise FileNotFoundError(f"Không tìm thấy tệp phụ đề: {self.srt_path}")
            
            os.makedirs(self.output_dir, exist_ok=True)
            # Tạo tên file output tăng dần: TPL_heygen.mp4, TPL_heygen01.mp4, TPL_heygen02.mp4...
            base_output_name = "TPL_heygen"
            ext_part = ".mp4"
            output_video_path = os.path.join(self.output_dir, f"{base_output_name}{ext_part}")
            if os.path.exists(output_video_path):
                counter = 1
                while True:
                    candidate = os.path.join(self.output_dir, f"{base_output_name}{counter:02d}{ext_part}")
                    if not os.path.exists(candidate):
                        output_video_path = candidate
                        break
                    counter += 1

            # Đọc nội dung file SRT
            self.log(f"📄 Đang đọc phụ đề SRT: {os.path.basename(self.srt_path)}")
            try:
                with open(self.srt_path, 'r', encoding='utf-8') as f:
                    srt_content = f.read()
            except UnicodeDecodeError:
                with open(self.srt_path, 'r', encoding='latin-1') as f:
                    srt_content = f.read()

            if not srt_content.strip():
                raise ValueError("Nội dung tệp SRT rỗng.")

            self.progress_updated.emit(5)
            if self._is_stopped:
                return

            # --- BƯỚC 1: PHÂN TÍCH SRT QUA GEMINI ---
            self.status_updated.emit("Đang kết nối tới Gemini...")
            self.controller = BrowserAutomationController(log_callback=self.log)
            
            # Khởi chạy trình duyệt (hiển thị giao diện để người dùng có thể theo dõi và tương tác)
            browser_ok = self.controller.setup_browser(profile_path=GOOGLE_PROFILE_PATH, headless=self.headless)
            if not browser_ok:
                raise RuntimeError("Không khởi động được Chrome. Đảm bảo Chrome không bị chiếm dụng hoặc cài đặt đúng.")

            if self._is_stopped:
                self.controller.cleanup()
                return

            # Kết nối Gemini
            if not self.controller.connect_to_gemini():
                raise RuntimeError("Không thể đăng nhập hoặc kết nối tới Gemini. Hãy ấn 'Đăng nhập Google' trên ứng dụng để cấu hình tài khoản trước.")

            self.progress_updated.emit(15)
            self.status_updated.emit("Đang phân tích phụ đề SRT bằng Gemini...")
            
            keywords_data = self.controller.analyze_srt(srt_content, self.n_keywords, self.custom_prompt)
            # Đóng trình duyệt ngay sau khi lấy xong kết quả phân tích sub
            self.controller.cleanup()
            
            if keywords_data:
                # Sắp xếp các từ khóa theo thời gian bắt đầu tăng dần
                from video_processor import srt_time_to_seconds
                
                def get_start_sec(item):
                    try:
                        return srt_time_to_seconds(item.get("start", "00:00:00"))
                    except Exception:
                        return 0.0

                sorted_items = sorted(keywords_data, key=get_start_sec)
                
                valid_items = []
                last_start_sec = -999.0
                for item in sorted_items:
                    start_sec = get_start_sec(item)
                    # 1. Từ khóa đầu tiên phải sau giây thứ 10
                    if start_sec < 10.0:
                        self.log(f"⚠️ Python lọc bỏ từ khóa '{item.get('keyword')}' vì xuất hiện trước giây thứ 10 ({item.get('start')})")
                        continue
                    # 2. Khoảng cách với từ khóa trước đó tối thiểu 10s
                    if start_sec - last_start_sec < 10.0:
                        self.log(f"⚠️ Python lọc bỏ từ khóa '{item.get('keyword')}' vì khoảng cách quá gần từ khóa trước ({start_sec - last_start_sec:.1f}s < 10s)")
                        continue
                    
                    valid_items.append(item)
                    last_start_sec = start_sec
                    
                keywords_data = valid_items
            
            if not keywords_data:
                raise RuntimeError("Phân tích SRT thất bại hoặc không có từ khóa nào thỏa mãn điều kiện thời gian (bắt đầu sau 10s và cách nhau ít nhất 10s).")

            self.progress_updated.emit(40)
            if self._is_stopped:
                return

            # --- BƯỚC 2: TẠO ẢNH AI QUA GOOGLE LABS FLOW ---
            self.status_updated.emit("Đang chuẩn bị tạo ảnh ngầm (qua API & NestJS)...")
            self.progress_updated.emit(50)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)

            # Khởi tạo danh sách các item cần sinh ảnh
            pending_items = []
            for idx, item in enumerate(keywords_data):
                pending_items.append({
                    "original_idx": idx,
                    "keyword": item.get("keyword", f"Key_{idx}"),
                    "start": item.get("start", ""),
                    "end": item.get("end", ""),
                    "prompt": item.get("prompt", "")
                })

            success_segments = {} # Lưu {original_idx: segment_dict}
            total_items = len(pending_items)
            
            # Vòng tạo ảnh (tối đa 4 vòng: vòng đầu + 3 vòng thử lại)
            max_rounds = 4
            for round_idx in range(max_rounds):
                if not pending_items:
                    break
                    
                if round_idx > 0:
                    self.log(f"\n🔄 [VÒNG THỬ LẠI {round_idx}/3] Đang tạo lại cho {len(pending_items)} từ khóa thất bại...")
                    time.sleep(3)
                    
                still_failed = []
                for item in pending_items:
                    if self._is_stopped:
                        return
                        
                    orig_idx = item["original_idx"]
                    keyword = item["keyword"]
                    start_time = item["start"]
                    end_time = item["end"]
                    prompt = item["prompt"]
                    
                    self.status_updated.emit(f"Đang sinh ảnh AI cho từ khóa ({orig_idx + 1}/{total_items}): {keyword}")
                    self.log(f"🎨 Từ khóa: '{keyword}' (Vòng {round_idx if round_idx > 0 else 'Đầu'})")
                    
                    # Gọi API sinh ảnh
                    b64_image = self.controller.generate_image_by_flow(
                        prompt, 
                        aspect_ratio=self.aspect_ratio, 
                        model=self.image_model
                    )
                    
                    if b64_image:
                        try:
                            img_path = os.path.join(temp_dir, f"img_{orig_idx}.png")
                            with open(img_path, 'wb') as img_f:
                                img_f.write(base64.b64decode(b64_image))
                            self.log(f"💾 Đã lưu ảnh thành công: {img_path}")
                            
                            from video_processor import srt_time_to_seconds
                            start_sec = srt_time_to_seconds(start_time)
                            success_segments[orig_idx] = {
                                "start_sec": start_sec,
                                "end_sec": start_sec + 5.0, # Cố định 5s hiển thị
                                "image_path": img_path
                            }
                        except Exception as save_err:
                            self.log(f"⚠️ Lỗi lưu ảnh cho {keyword}: {save_err}")
                            still_failed.append(item)
                    else:
                        self.log(f"❌ Tạo ảnh thất bại cho: {keyword}")
                        still_failed.append(item)
                        
                    # Cập nhật tiến độ tạo ảnh (chiếm từ 50% đến 80%)
                    img_progress = 50 + int((len(success_segments) / total_items) * 30)
                    self.progress_updated.emit(img_progress)
                    time.sleep(2) # Chờ nhẹ giữa các ảnh
                    
                pending_items = still_failed

            # Tắt trình duyệt giải phóng bộ nhớ
            self.log("🧹 Hoàn thành tác vụ trình duyệt. Đang đóng Chrome...")
            self.controller.cleanup()
            self.controller = None

            # Nếu vẫn còn ảnh lỗi sau 3 lần thử lại
            if pending_items:
                failed_keywords = [item["keyword"] for item in pending_items]
                self.log(f"\n⚠️ CẢNH BÁO: Không thể tạo được ảnh cho {len(failed_keywords)} từ khóa sau 3 lần thử lại: {failed_keywords}")
                
                # Yêu cầu người dùng quyết định qua UI
                self.user_decision = None
                self.user_decision_requested.emit(failed_keywords)
                
                # Chờ người dùng click nút trên Popup
                self.log("⏳ Đang chờ người dùng đưa ra lựa chọn trên Popup...")
                while self.user_decision is None:
                    if self._is_stopped:
                        return
                    self.msleep(100)
                    
                if self.user_decision == "retry":
                    self.log("🛑 Người dùng chọn KHÔNG (chạy lại toàn bộ từ đầu). Đang dọn dẹp để khởi động lại...")
                    raise RuntimeError("USER_RETRY_REQUESTED")
                else:
                    self.log("✅ Người dùng chọn CÓ (tiếp tục ghép video với các ảnh đã tạo thành công).")

            # Chuẩn bị danh sách segments thành công để truyền vào FFmpeg
            segments = [success_segments[k] for k in sorted(success_segments.keys())]
            
            if not segments:
                raise ValueError("Không tạo được bất kỳ hình ảnh nào từ danh sách từ khóa.")

            self.progress_updated.emit(82)
            if self._is_stopped:
                return

            # --- BƯỚC 3: XỬ LÝ VIDEO BẰNG FFMPEG ---
            self.status_updated.emit("Đang thay thế hình ảnh trong video bằng FFmpeg...")
            self.log("🎬 Bắt đầu quá trình thay thế hình ảnh bằng FFmpeg overlay...")
            
            ffmpeg_ok = replace_video_segments(
                video_path=self.video_path,
                segments=segments,
                output_path=output_video_path,
                log_callback=self.log
            )
            
            if not ffmpeg_ok:
                raise RuntimeError("FFmpeg xử lý ghép đè hình ảnh thất bại. Kiểm tra lại log chi tiết phía trên.")

            self.progress_updated.emit(98)
            
            # --- BƯỚC 4: DỌN DẸP FILE TẠM ---
            self.status_updated.emit("Đang dọn dẹp các tệp tạm thời...")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                self.log("🧹 Đã xóa sạch thư mục ảnh tạm thời.")

            self.progress_updated.emit(100)
            self.status_updated.emit("Quy trình hoàn tất thành công!")
            self.log(f"\n🎉 XỬ LÝ HOÀN THÀNH!")
            self.log(f"🎥 Video mới đã được xuất tại: {output_video_path}")
            self.finished.emit(output_video_path)

        except Exception as e:
            # Dọn dẹp khẩn cấp khi lỗi
            if self.controller:
                try:
                    self.controller.cleanup()
                except Exception:
                    pass
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
            
            error_details = traceback.format_exc()
            self.log(f"💥 Lỗi nghiêm trọng: {e}\n{error_details}")
            self.error_occurred.emit(str(e))
