import os
import sys
import json
from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QFileDialog, QSizePolicy, QStackedWidget
)
from PySide6.QtGui import QIcon, QFont, QTextCursor

from qfluentwidgets import (
    setTheme, Theme, PushButton, PrimaryPushButton, LineEdit, SpinBox,
    ProgressBar, TextEdit, InfoBar, InfoBarPosition, TitleLabel,
    SubtitleLabel, FluentIcon, CardWidget, MessageDialog, DoubleSpinBox,
    ComboBox, Pivot
)

from app_worker import AppWorker, GOOGLE_PROFILE_PATH
from browser_controller import open_google_login_browser

# Thư mục gốc của dự án
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "app_config.json")

class VideoVisualReplacerUI(QWidget):
    """Giao diện chính của ứng dụng phong cách Fluent Design (Light Theme)"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.captcha_process = None
        self.init_ui()
        self.load_config()
        self.start_captcha_server()

    def start_captcha_server(self):
        """Khởi động file CaptchaServer.exe chạy ngầm."""
        import subprocess
        captcha_exe = os.path.join(BASE_DIR, "CaptchaServer.exe")
        if os.path.exists(captcha_exe):
            try:
                self.txt_log.append("🔌 Đang khởi động Captcha Server (cổng 3000)...")
                
                # Cấu hình để chạy ngầm không hiện cửa sổ console
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    
                self.captcha_process = subprocess.Popen(
                    [captcha_exe],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    cwd=BASE_DIR
                )
                self.txt_log.append("✅ Khởi động Captcha Server thành công.")
            except Exception as e:
                self.txt_log.append(f"⚠️ Không thể khởi động CaptchaServer.exe: {e}")
        else:
            self.txt_log.append("⚠️ Cảnh báo: Không tìm thấy file CaptchaServer.exe tại thư mục gốc.")

    def init_ui(self):
        # Thiết lập Theme Sáng (Fluent Design)
        setTheme(Theme.LIGHT)
        
        self.setWindowTitle("TPL Heygen")
        self.resize(750, 650)
        self.setMinimumSize(700, 600)
        
        logo_path = os.path.join(BASE_DIR, "logo.ico")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        
        # Font chữ mặc định
        font = QFont("Segoe UI", 10)
        self.setFont(font)

        # Layout chính
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(15)

        # --- TIÊU ĐỀ HỆ THỐNG ---
        title_layout = QHBoxLayout()
        logo_label = TitleLabel("TPL Heygen")
        logo_label.setStyleSheet("color: #0078d4; font-weight: bold;")
        title_layout.addWidget(logo_label)
        
        version_label = SubtitleLabel("v1.0.0")
        version_label.setStyleSheet("color: #64748b; font-size: 13px; margin-top: 10px;")
        title_layout.addWidget(version_label)
        
        title_layout.addStretch()
        
        author_label = SubtitleLabel("Tác giả: Lý Trần | Zalo: 0398029854")
        author_label.setStyleSheet("color: #0f766e; font-size: 12px; font-weight: 500; margin-top: 10px;")
        title_layout.addWidget(author_label)
        
        main_layout.addLayout(title_layout)

        # --- TAB NAVIGATION (PIVOT) ---
        self.pivot = Pivot(self)
        self.stacked_widget = QStackedWidget(self)
        
        # Trang 1: Công cụ chính
        self.page_tools = QWidget()
        tools_layout = QVBoxLayout(self.page_tools)
        tools_layout.setContentsMargins(0, 5, 0, 0)
        tools_layout.setSpacing(15)

        # --- CARD CẤU HÌNH ĐẦU VÀO ---
        config_card = CardWidget(self.page_tools)
        config_card.setStyleSheet("CardWidget { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; }")
        card_layout = QVBoxLayout(config_card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(12)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        # 1. Chọn Video
        grid_layout.addWidget(SubtitleLabel("Chọn Video:"), 0, 0)
        self.txt_video = LineEdit()
        self.txt_video.setPlaceholderText("Đường dẫn file video (.mp4, .mkv, .avi,...)")
        grid_layout.addWidget(self.txt_video, 0, 1)
        self.btn_browse_video = PushButton(FluentIcon.VIDEO, "Chọn file")
        self.btn_browse_video.clicked.connect(self.browse_video)
        grid_layout.addWidget(self.btn_browse_video, 0, 2)

        # 2. Chọn Phụ đề SRT
        grid_layout.addWidget(SubtitleLabel("Chọn file SRT:"), 1, 0)
        self.txt_srt = LineEdit()
        self.txt_srt.setPlaceholderText("Đường dẫn file phụ đề SRT (.srt)")
        grid_layout.addWidget(self.txt_srt, 1, 1)
        self.btn_browse_srt = PushButton(FluentIcon.DOCUMENT, "Chọn file")
        self.btn_browse_srt.clicked.connect(self.browse_srt)
        grid_layout.addWidget(self.btn_browse_srt, 1, 2)

        # 3. Chọn số từ khóa N
        grid_layout.addWidget(SubtitleLabel("Số lượng ảnh:"), 2, 0)
        self.spin_n = SpinBox()
        self.spin_n.setRange(1, 50)
        self.spin_n.setValue(5)
        self.spin_n.setFixedWidth(100)
        grid_layout.addWidget(self.spin_n, 2, 1, Qt.AlignLeft)

        # 4. Chọn thư mục xuất
        grid_layout.addWidget(SubtitleLabel("Thư mục xuất:"), 3, 0)
        self.txt_output_dir = LineEdit()
        self.txt_output_dir.setPlaceholderText("Thư mục chứa video đầu ra")
        grid_layout.addWidget(self.txt_output_dir, 3, 1)
        self.btn_browse_output = PushButton(FluentIcon.FOLDER, "Chọn thư mục")
        self.btn_browse_output.clicked.connect(self.browse_output)
        grid_layout.addWidget(self.btn_browse_output, 3, 2)

        # 5. Chọn Model ảnh
        grid_layout.addWidget(SubtitleLabel("Model tạo ảnh:"), 4, 0)
        self.cb_model = ComboBox()
        self.cb_model.addItems(["GEM_PIX_2", "IMAGEN_3_FAST", "IMAGEN_2"])
        self.cb_model.setCurrentIndex(0)
        self.cb_model.setFixedWidth(200)
        self.cb_model.currentIndexChanged.connect(self.save_config)
        grid_layout.addWidget(self.cb_model, 4, 1, Qt.AlignLeft)

        # 6. Chọn kích thước ảnh (Tỷ lệ)
        grid_layout.addWidget(SubtitleLabel("Kích thước ảnh:"), 5, 0)
        self.cb_ratio = ComboBox()
        self.cb_ratio.addItems(["16:9", "9:16", "1:1"])
        self.cb_ratio.setCurrentIndex(0)
        self.cb_ratio.setFixedWidth(200)
        self.cb_ratio.currentIndexChanged.connect(self.save_config)
        grid_layout.addWidget(self.cb_ratio, 5, 1, Qt.AlignLeft)

        # 7. Prompt tùy chỉnh (Style bổ sung)
        grid_layout.addWidget(SubtitleLabel("Prompt (Style):"), 6, 0)
        self.txt_custom_prompt = LineEdit()
        self.txt_custom_prompt.setPlaceholderText("Ví dụ: Vietnam traditional style, USA traditional style, photorealistic...")
        self.txt_custom_prompt.textChanged.connect(self.save_config)
        grid_layout.addWidget(self.txt_custom_prompt, 6, 1)

        card_layout.addLayout(grid_layout)
        tools_layout.addWidget(config_card)

        # --- NÚT ĐIỀU KHIỂN & ĐĂNG NHẬP ---
        action_layout = QHBoxLayout()
        action_layout.setSpacing(15)

        # Nút Đăng nhập Google (Gemini)
        self.btn_login_google = PushButton(FluentIcon.PEOPLE, "Google")
        self.btn_login_google.clicked.connect(self.login_google)
        action_layout.addWidget(self.btn_login_google)

        # Nút Lấy Token & Project ID tự động
        self.btn_get_token = PushButton(FluentIcon.PEOPLE, "Lấy Token")
        self.btn_get_token.clicked.connect(self.get_token_automatically)
        action_layout.addWidget(self.btn_get_token)

        # Nút Xóa Profile
        self.btn_delete_profile = PushButton(FluentIcon.DELETE, "Xóa Profile")
        self.btn_delete_profile.clicked.connect(self.delete_google_profile)
        action_layout.addWidget(self.btn_delete_profile)

        action_layout.addStretch()

        # Nút Dừng hẳn
        self.btn_cancel = PushButton(FluentIcon.CANCEL, "Dừng hẳn")
        self.btn_cancel.clicked.connect(self.stop_process)
        self.btn_cancel.setEnabled(False)
        action_layout.addWidget(self.btn_cancel)

        # Nút Bắt đầu
        self.btn_start = PrimaryPushButton(FluentIcon.PLAY, "Bắt đầu xử lý")
        self.btn_start.clicked.connect(self.start_process)
        action_layout.addWidget(self.btn_start)

        tools_layout.addLayout(action_layout)

        # --- THÔNG TIN TIẾN TRÌNH ---
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        
        self.lbl_status = SubtitleLabel("Sẵn sàng.")
        self.lbl_status.setStyleSheet("color: #475569; font-size: 13px;")
        progress_layout.addWidget(self.lbl_status)

        self.progress_bar = ProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        tools_layout.addLayout(progress_layout)

        # --- MÀN HÌNH LOGS ---
        log_card = CardWidget(self.page_tools)
        log_card_layout = QVBoxLayout(log_card)
        log_card_layout.setContentsMargins(10, 10, 10, 10)
        
        self.txt_log = TextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("Logs quá trình chạy thời gian thực sẽ hiển thị tại đây...")
        self.txt_log.setStyleSheet(
            "TextEdit { background-color: #0f172a; color: #38bdf8; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; border-radius: 6px; }"
        )
        log_card_layout.addWidget(self.txt_log)
        tools_layout.addWidget(log_card)

        # Trang 2: Hướng dẫn & Cài đặt
        self.page_help = QWidget()
        help_layout = QVBoxLayout(self.page_help)
        help_layout.setContentsMargins(0, 5, 0, 0)
        help_layout.setSpacing(15)

        help_card = CardWidget(self.page_help)
        help_card.setStyleSheet("CardWidget { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; }")
        card_help_layout = QVBoxLayout(help_card)
        card_help_layout.setContentsMargins(20, 20, 20, 20)
        card_help_layout.setSpacing(15)
        
        help_title = TitleLabel("Cài đặt Extension TPL Helper")
        help_title.setStyleSheet("font-size: 18px; color: #1e293b; font-weight: bold;")
        card_help_layout.addWidget(help_title)
        
        help_subtitle = SubtitleLabel("Extension giúp hỗ trợ bắt Token và Cookies tự động từ Google Labs Flow.")
        help_subtitle.setStyleSheet("font-size: 13px; color: #64748b;")
        card_help_layout.addWidget(help_subtitle)
        
        # Nút xuất Extension
        self.btn_export_ext = PrimaryPushButton(FluentIcon.DOWNLOAD, "Xuất Extension TPL_extension")
        self.btn_export_ext.clicked.connect(self.export_extension)
        self.btn_export_ext.setFixedWidth(260)
        card_help_layout.addWidget(self.btn_export_ext)
        
        # Hướng dẫn chi tiết bằng HTML TextEdit
        self.txt_guide = TextEdit()
        self.txt_guide.setReadOnly(True)
        self.txt_guide.setHtml("""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #334155; line-height: 1.6;">
                <h3 style="color: #0f766e; margin-top: 0; font-size: 15px; font-weight: bold;">Các bước cài đặt Extension vào trình duyệt Chrome:</h3>
                <ol style="margin-left: 0; padding-left: 20px;">
                    <li>Nhấn nút <b>"Xuất Extension TPL_extension"</b> ở trên và chọn thư mục để lưu tiện ích ra máy tính của bạn.</li>
                    <li>Mở trình duyệt <b>Google Chrome</b> (hoặc các trình duyệt Chromium như Edge, Cốc Cốc) của bạn.</li>
                    <li>Truy cập vào trang quản lý tiện ích bằng cách nhập đường dẫn sau vào thanh địa chỉ: <br>
                        <span style="background-color: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-weight: bold;">chrome://extensions/</span>
                    </li>
                    <li>Bật tùy chọn <b>"Chế độ dành cho nhà phát triển" (Developer mode)</b> ở góc trên bên phải màn hình.</li>
                    <li>Nhấn nút <b>"Tải tiện ích đã giải nén" (Load unpacked)</b> hiển thị ở góc trên bên trái.</li>
                    <li>Chọn đúng thư mục <b>TPL_extension</b> mà bạn vừa xuất ra ở Bước 1.</li>
                </ol>
                <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; padding: 10px; border-radius: 6px; color: #166534; margin-top: 10px;">
                    🎯 <b>Lưu ý quan trọng:</b> Sau khi cài đặt thành công, extension <b>TPL Heygen Capture Helper</b> sẽ tự động hoạt động để hỗ trợ bạn bắt Bearer Token Google Labs mà không cần bất kỳ thao tác thủ công nào khác!
                </div>
            </div>
        """)
        self.txt_guide.setStyleSheet("TextEdit { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; }")
        card_help_layout.addWidget(self.txt_guide)
        
        help_layout.addWidget(help_card)

        # Thêm các trang vào stacked_widget
        self.stacked_widget.addWidget(self.page_tools)
        self.stacked_widget.addWidget(self.page_help)
        
        self.pivot.addItem("tools_tab", "Công cụ", lambda: self.stacked_widget.setCurrentWidget(self.page_tools))
        self.pivot.addItem("help_tab", "Hướng dẫn & Cài đặt", lambda: self.stacked_widget.setCurrentWidget(self.page_help))
        self.pivot.setCurrentItem("tools_tab")
        
        main_layout.addWidget(self.pivot)
        main_layout.addWidget(self.stacked_widget)

    def export_extension(self):
        """Xuất thư mục extension ra thư mục do người dùng chọn dưới tên TPL_extension."""
        dest_dir = QFileDialog.getExistingDirectory(self, "Chọn thư mục để xuất Extension")
        if not dest_dir:
            return
            
        src_ext = os.path.join(BASE_DIR, "extension")
        if not os.path.exists(src_ext):
            InfoBar.error(
                title="Lỗi xuất Extension",
                content="Không tìm thấy thư mục extension gốc trong thư mục dự án.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self
            )
            return
            
        dest_ext = os.path.join(dest_dir, "TPL_extension")
        try:
            import shutil
            if os.path.exists(dest_ext):
                shutil.rmtree(dest_ext)
            shutil.copytree(src_ext, dest_ext)
            
            # Hiển thị thông báo thành công
            InfoBar.success(
                title="Xuất thành công",
                content=f"Đã xuất Extension sang: {dest_ext}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                title="Lỗi xuất Extension",
                content=f"Không thể sao chép thư mục extension: {e}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    # --- HÀM XỬ LÝ CHỌN FILE/THƯ MỤC ---

    def browse_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn Video đầu vào", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.flv)"
        )
        if file_path:
            self.txt_video.setText(file_path)
            self.save_config()

    def browse_srt(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file phụ đề SRT", "", "Subtitle Files (*.srt)"
        )
        if file_path:
            self.txt_srt.setText(file_path)
            self.save_config()

    def browse_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn Thư mục xuất kết quả")
        if dir_path:
            self.txt_output_dir.setText(dir_path)
            self.save_config()

    # --- LƯU & LOAD CẤU HÌNH ---

    def save_config(self):
        config_data = {
            "n_keywords": self.spin_n.value(),
            "output_dir": self.txt_output_dir.text(),
            "image_model": self.cb_model.currentText(),
            "aspect_ratio": self.cb_ratio.currentText(),
            "custom_prompt": self.txt_custom_prompt.text()
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self.spin_n.setValue(config_data.get("n_keywords", 5))
                    self.txt_output_dir.setText(config_data.get("output_dir", ""))
                    
                    model = config_data.get("image_model", "GEM_PIX_2")
                    idx_model = self.cb_model.findText(model)
                    if idx_model >= 0:
                        self.cb_model.setCurrentIndex(idx_model)
                        
                    ratio = config_data.get("aspect_ratio", "16:9")
                    idx_ratio = self.cb_ratio.findText(ratio)
                    if idx_ratio >= 0:
                        self.cb_ratio.setCurrentIndex(idx_ratio)
                        
                    self.txt_custom_prompt.setText(config_data.get("custom_prompt", ""))
            except Exception:
                pass

    # --- HÀM THỰC THI CHÍNH ---

    def login_google(self):
        """Mở Chrome hệ thống để đăng nhập tài khoản Google (Gemini)."""
        self.btn_login_google.setEnabled(False)
        self.btn_get_token.setEnabled(False)
        self.txt_log.clear()
        self.txt_log.append("🔓 Đang mở trình duyệt Chrome thật để cấu hình tài khoản...")
        self.txt_log.append("👉 BƯỚC 1: Hãy đăng nhập tài khoản Google của bạn trên TAB 1 (Gemini) để phục vụ việc phân tích phụ đề.")
        self.txt_log.append("👉 BƯỚC 2: Sau khi đăng nhập thành công, hãy ĐÓNG CỬA SỔ TRÌNH DUYỆT CHROME ĐÓ LẠI để lưu session.")
        
        # Mở login trong background thread để tránh khóa UI
        class LoginThread(QThread):
            finished = Signal(bool)
            def run(self):
                ok = open_google_login_browser(GOOGLE_PROFILE_PATH)
                self.finished.emit(ok)
        
        self.login_thread = LoginThread(self)
        self.login_thread.finished.connect(self.on_login_finished)
        self.login_thread.start()

    def on_login_finished(self, success):
        self.btn_login_google.setEnabled(True)
        self.btn_get_token.setEnabled(True)
        if success:
            self.txt_log.append("✅ Đã lưu cấu hình đăng nhập thành công. Bạn có thể bắt đầu xử lý.")
            InfoBar.success(
                title="Đăng nhập",
                content="Lưu cấu hình trình duyệt Google thành công!",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        else:
            self.txt_log.append("❌ Mở trình duyệt đăng nhập thất bại.")

    def get_token_automatically(self):
        """Mở Chrome để tự động đăng nhập, lấy token và tạo project ID."""
        self.btn_get_token.setEnabled(False)
        self.btn_login_google.setEnabled(False)
        self.txt_log.clear()
        
        class TokenExtractThread(QThread):
            finished = Signal(bool)
            log_signal = Signal(str)
            
            def run(self):
                from browser_controller import BrowserAutomationController
                controller = BrowserAutomationController(log_callback=self.log_signal.emit)
                ok = controller.auto_extract_credentials_and_create_project(self.log_signal.emit)
                self.finished.emit(ok)
                
        self.token_thread = TokenExtractThread(self)
        self.token_thread.log_signal.connect(self.txt_log.append)
        self.token_thread.finished.connect(self.on_token_finished)
        self.token_thread.start()

    def on_token_finished(self, success):
        self.btn_get_token.setEnabled(True)
        self.btn_login_google.setEnabled(True)
        if success:
            InfoBar.success(
                title="Lấy Token",
                content="Lấy Token & Project ID tự động thành công!",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        else:
            InfoBar.error(
                title="Lấy Token",
                content="Lấy Token tự động thất bại. Hãy xem chi tiết logs.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def start_process(self):
        """Bắt đầu quá trình tự động phân tích và ghép video."""
        video = self.txt_video.text().strip()
        srt = self.txt_srt.text().strip()
        n = self.spin_n.value()
        output = self.txt_output_dir.text().strip()

        if not video or not srt or not output:
            InfoBar.warning(
                title="Thiếu thông tin",
                content="Vui lòng chọn đầy đủ Video, Phụ đề và Thư mục xuất.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3500,
                parent=self
            )
            return

        # Lưu lại cấu hình lựa chọn
        self.save_config()

        # Cấu hình UI khi chạy
        self.btn_start.setEnabled(False)
        self.btn_login_google.setEnabled(False)
        self.btn_get_token.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.txt_log.clear()
        self.progress_bar.setValue(0)

        # Khởi tạo AppWorker chạy nền (headless=True để chạy ẩn hoàn toàn Chrome khi phân tích Gemini)
        self.worker = AppWorker(
            video_path=video,
            srt_path=srt,
            n_keywords=n,
            output_dir=output,
            image_model=self.cb_model.currentText(),
            aspect_ratio=self.cb_ratio.currentText(),
            custom_prompt=self.txt_custom_prompt.text(),
            headless=True,
            parent=self
        )

        # Kết nối các tín hiệu Signal
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.status_updated.connect(self.on_status)
        self.worker.log_message.connect(self.on_log)
        self.worker.finished.connect(self.on_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.user_decision_requested.connect(self.on_user_decision_requested)

        self.worker.start()

    def stop_process(self):
        """Dừng hoàn toàn tiến trình chạy nền và đóng các tác vụ liên quan."""
        if self.worker and self.worker.isRunning():
            self.btn_cancel.setEnabled(False)
            self.txt_log.append("🛑 Đang dừng hẳn tiến trình chạy nền và giải phóng trình duyệt...")
            self.worker.stop()
            
            # Đợi luồng tự dừng trong tối đa 5 giây trước khi buộc đóng (force terminate)
            import time
            start_wait = time.time()
            while self.worker.isRunning() and time.time() - start_wait < 5.0:
                QApplication.processEvents()
                time.sleep(0.1)

            if self.worker.isRunning():
                self.txt_log.append("⚠️ Luồng không tự dừng, tiến hành buộc dừng (force terminate)...")
                self.worker.terminate()
                self.worker.wait()
            
            # Giải phóng và tắt các tiến trình Chrome còn chạy ngầm của profile này
            try:
                from browser_controller import kill_chrome_by_profile
                from app_worker import GOOGLE_PROFILE_PATH
                kill_chrome_by_profile(GOOGLE_PROFILE_PATH)
            except Exception:
                pass

            self.txt_log.append("✅ Đã dừng hẳn tiến trình chạy nền. Trình duyệt đã được giải phóng.")
            self.progress_bar.setValue(0)
            self.lbl_status.setText("Đã dừng hẳn. Sẵn sàng chạy lại.")
            self.reset_ui_state()

    def delete_google_profile(self):
        """Xóa thư mục profile Google cũ."""
        dialog = MessageDialog(
            "Xác nhận xóa",
            "Bạn có chắc chắn muốn xóa Profile cũ không?\nHành động này sẽ yêu cầu bạn đăng nhập lại tài khoản Google từ đầu.",
            self
        )
        dialog.yesSignal.connect(self._do_delete_profile)
        dialog.exec()

    def _do_delete_profile(self):
        import shutil
        profiles_dir = os.path.join(BASE_DIR, "profiles")
        if os.path.exists(profiles_dir):
            try:
                # Trước khi xóa, giải phóng tiến trình Chrome ngầm
                try:
                    from browser_controller import kill_chrome_by_profile
                    kill_chrome_by_profile(GOOGLE_PROFILE_PATH)
                except Exception:
                    pass
                    
                shutil.rmtree(profiles_dir)
                self.txt_log.append("🗑️ Đã xóa sạch thư mục profiles trong dự án để sẵn sàng đăng nhập tài khoản mới.")
                InfoBar.success(
                    title="Xóa Profile",
                    content="Đã xóa toàn bộ thư mục Profiles thành công!",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            except Exception as e:
                self.txt_log.append(f"❌ Không thể xóa thư mục profiles. Có thể trình duyệt Chrome đang chạy ngầm chiếm dụng: {e}")
                self.txt_log.append("👉 Vui lòng nhấn nút 'Dừng hẳn' hoặc đóng toàn bộ Chrome rồi thử lại.")
        else:
            self.txt_log.append("ℹ️ Không tìm thấy thư mục profiles để xóa.")

    # --- SLOT XỬ LÝ SIGNALS TỪ WORKER ---

    def on_progress(self, val):
        self.progress_bar.setValue(val)

    def on_status(self, text):
        self.lbl_status.setText(text)

    def on_log(self, text):
        self.txt_log.append(text)
        # Tự động cuộn xuống dưới cùng
        self.txt_log.moveCursor(QTextCursor.End)

    def on_finished(self, output_file):
        self.reset_ui_state()
        self.lbl_status.setText("Hoàn thành công việc!")
        
        dialog = MessageDialog(
            "Hoàn thành",
            f"Quá trình thay thế hình ảnh video thành công!\n\nVideo lưu tại:\n{output_file}",
            self
        )
        dialog.exec()

    def on_error(self, err_msg):
        self.reset_ui_state()
        
        # Nếu là yêu cầu chạy lại từ người dùng
        if err_msg == "USER_RETRY_REQUESTED":
            self.txt_log.append("\n🔄 ĐANG TỰ ĐỘNG KHỞI ĐỘNG LẠI QUY TRÌNH THEO YÊU CẦU...")
            self.start_process()
            return
            
        self.lbl_status.setText(f"Lỗi: {err_msg}")
        
        dialog = MessageDialog(
            "Gặp lỗi xảy ra",
            f"Tiến trình bị gián đoạn do lỗi:\n{err_msg}",
            self
        )
        dialog.exec()

    def on_user_decision_requested(self, failed_keywords):
        """Mở popup hỏi người dùng khi có ảnh sinh lỗi sau 3 lần thử lại."""
        keywords_str = "\n".join([f"- {k}" for k in failed_keywords])
        
        dialog = MessageDialog(
            "Cảnh báo sinh ảnh lỗi",
            f"Không thể tạo được ảnh cho các từ khóa sau sau 3 lần thử lại:\n{keywords_str}\n\n"
            f"Bạn có muốn tiếp tục ghép video mà không cần những ảnh này không?",
            self
        )
        # Thay đổi văn bản hiển thị của các nút
        dialog.yesButton.setText("Có (Tiếp tục ghép)")
        dialog.cancelButton.setText("Không (Chạy lại từ đầu)")
        
        # Kết nối sự kiện Có/Không
        dialog.yesSignal.connect(lambda: self.handle_decision(dialog, "continue"))
        dialog.cancelSignal.connect(lambda: self.handle_decision(dialog, "retry"))
        dialog.exec()

    def handle_decision(self, dialog, choice):
        if self.worker:
            self.worker.user_decision = choice
        dialog.close()

    def reset_ui_state(self):
        self.btn_start.setEnabled(True)
        self.btn_login_google.setEnabled(True)
        self.btn_get_token.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.worker = None

    def closeEvent(self, event):
        """Đóng cửa sổ ứng dụng và dọn dẹp các tiến trình ngầm."""
        if hasattr(self, 'captcha_process') and self.captcha_process:
            try:
                self.txt_log.append("🔌 Đang dừng Captcha Server...")
                self.captcha_process.terminate()
                self.captcha_process.wait(timeout=2)
            except Exception:
                try:
                    self.captcha_process.kill()
                except Exception:
                    pass
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Thiết lập icon nếu có
    # app.setWindowIcon(QIcon("icon.png"))
    
    ui = VideoVisualReplacerUI()
    ui.show()
    sys.exit(app.exec())
