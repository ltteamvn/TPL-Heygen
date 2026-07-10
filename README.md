# TPL Heygen - Công Cụ Tự Động Hóa Ghép Ảnh AI Vào Video

**TPL Heygen** là ứng dụng desktop chuyên nghiệp giúp tự động hóa toàn bộ quy trình: phân tích kịch bản từ phụ đề SRT bằng Gemini AI ngầm, tự động lấy Token và sinh ảnh AI từ Google Labs Flow, áp dụng hiệu ứng chuyển động Ken Burns mượt mà và ghép đè hình ảnh vào video gốc bằng FFmpeg.

---

## 🌟 Các Tính Năng Nổi Bật

1. **Tự Động Hóa Lấy Token & Project ID:** 
   - Selenium tự động điều hướng và click nút `"Create with Google Flow"` trên trang chủ Google Labs để lấy phiên làm việc, tự động trích xuất Bearer Token và Project ID chỉ trong 3-5 giây.
2. **Giải Captcha Ngầm Tự Động:**
   - Ứng dụng tự động quản lý vòng đời và chạy ngầm tệp `CaptchaServer.exe` ở cổng 3000 để giải Recapcha mà không hiển thị cửa sổ CMD đen làm phiền người dùng.
3. **Phân Tích SRT Ẩn Danh:**
   - Trình duyệt Chrome phân tích kịch bản SRT qua Gemini được chạy ẩn nền hoàn toàn (`headless=True`).
4. **Hiệu Ứng Ảnh Động Chuyển Cảnh Mượt Mà (Ken Burns & Fade):**
   - Áp dụng ngẫu nhiên 4 hiệu ứng chuyển động chậm cực đẹp: *Zoom In*, *Zoom Out*, *Pan Trái-Sang-Phải*, *Pan Phải-Sang-Trái*.
   - Khử hoàn toàn hiện tượng rung lắc/giật hình (jitter) bằng cách bọc thuật toán tọa độ pixel FFmpeg bằng hàm `trunc()`.
   - Mỗi hình ảnh mặc định sẽ hiển thị cố định **5.0 giây** và chuyển cảnh mượt mà bằng hiệu ứng Fade In / Out 0.5s (kênh alpha).
5. **Cơ Chế Thử Lại Tạo Ảnh Thông Minh:**
   - Tự động thử lại tối đa 3 vòng cho các ảnh bị lỗi.
   - Nếu vẫn lỗi, hiển thị Popup hỏi người dùng:
     - **Có (Tiếp tục):** Ghép đè video với các ảnh đã sinh thành công.
     - **Không (Chạy lại):** Tự động dọn dẹp và chạy lại quy trình từ đầu.
6. **Hỗ Trợ Chạy Độc Lập / Offline (Chrome Portable):**
   - Nếu bạn đặt thư mục `chrome_bin` chứa sẵn trình duyệt `chrome.exe` (Chrome Portable) và `chromedriver.exe` vào thư mục dự án, ứng dụng sẽ chạy offline hoàn toàn, độc lập không phụ thuộc vào Chrome cài trên hệ thống máy khách, loại bỏ 100% lỗi lệch phiên bản Chrome.
7. **Đặt Tên File Xuất Thông Minh:**
   - Tên video đầu ra sẽ tự động tăng chỉ số (`TPL_heygen.mp4`, `TPL_heygen01.mp4`, `TPL_heygen02.mp4`...) để tránh ghi đè làm mất video cũ.

---

## 🛠️ Hướng Dẫn Cài Đặt & Sử Dụng

### 1. Yêu Cầu Hệ Thống
- Hệ điều hành: Windows 10 / 11.
- Python: Phiên bản 3.10 trở lên.
- Đã cài đặt phần mềm FFmpeg (nếu chạy offline thì đặt bộ ffmpeg vào thư mục `ffmpeg/` gốc của dự án).

### 2. Cài Đặt Thư Viện
Mở CMD/PowerShell tại thư mục dự án và chạy lệnh sau để cài đặt các thư viện cần thiết:
```bash
pip install PySide6 qfluentwidgets selenium requests urllib3 certifi idna charset-normalizer websocket-client undetected-chromedriver
```

### 3. Chạy Ứng Dụng
```bash
python main.py
```

---

## 📦 Hướng Dẫn Đóng Gói Phần Mềm (Build EXE)

### Bước 1: Biên Dịch Bằng Nuitka
Nhấn đúp chuột để chạy tệp [build.bat](build.bat).
* Script này sẽ gọi Nuitka biên dịch code local thành file thực thi mã máy ẩn console (`--windows-disable-console`).
* Đồng thời chạy script [copy_packages.py](copy_packages.py) tự động thu thập toàn bộ thư viện liên quan (`PySide6`, `qfluentwidgets`, `selenium`...) cùng các tài nguyên (`ffmpeg/`, `extension/`, `chrome_bin/`, `logo.ico`, `CaptchaServer.exe`) vào thư mục phân phối độc lập `build_out/TPL_Heygen.dist`.

### Bước 2: Tạo File Setup Cài Đặt Bằng Inno Setup
1. Tải và cài đặt phần mềm [Inno Setup Compiler](https://jrsoftware.org/isinfo.php) trên Windows.
2. Mở file [setup.iss](setup.iss) bằng Inno Setup.
3. Nhấn nút **Compile** (phím tắt `F9`). Trình biên dịch sẽ nén toàn bộ thư mục build thành file cài đặt duy nhất mang tên **`TPL_Heygen_Setup.exe`** nằm trong thư mục `build_out`.

---

## ✉️ Liên Hệ Tác Giả

Nếu bạn gặp khó khăn trong quá trình sử dụng, cần hỗ trợ kỹ thuật hoặc tùy biến thêm tính năng, xin vui lòng liên hệ:

* **Tác giả:** Lý Trần
* **Zalo:** [0398029854](https://zalo.me/0398029854)
* **GitHub Project:** [https://github.com/ltteamvn/TPL-Heygen](https://github.com/ltteamvn/TPL-Heygen)

*Bản quyền phần mềm thuộc về tác giả Lý Trần. Vui lòng không sao chép hoặc phân phối trái phép.*
