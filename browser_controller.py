import os
import time
import logging
import json
import ssl
import re
import uuid
import base64
import subprocess
import pyperclip
from typing import Callable, Optional, List, Dict, Tuple

# Bypass SSL certificate verification globally
os.environ['PYTHONHTTPSVERIFY'] = '0'
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

logger = logging.getLogger(__name__)

# Thư mục gốc của dự án
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_windows_download_path() -> str:
    """Lấy đường dẫn thư mục Downloads mặc định của hệ thống Windows."""
    try:
        import winreg
        sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
            val, _ = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')
            return str(val)
    except Exception:
        return os.path.join(os.path.expanduser('~'), 'Downloads')

def find_system_chrome() -> Optional[str]:
    """Tìm đường dẫn Google Chrome thật cài đặt trên hệ thống Windows."""
    candidate_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return None

def get_chrome_major_version() -> Optional[int]:
    """Lấy phiên bản chính (major version) của Google Chrome cài trên Windows."""
    import winreg
    paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Google\Chrome\BLBeacon"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome")
    ]
    
    for hive, path in paths:
        try:
            key = winreg.OpenKey(hive, path)
            for val_name in ["version", "DisplayVersion"]:
                try:
                    val, _ = winreg.QueryValueEx(key, val_name)
                    if val:
                        match = re.match(r'^(\d+)', str(val).strip())
                        if match:
                            winreg.CloseKey(key)
                            return int(match.group(1))
                except WindowsError:
                    pass
            winreg.CloseKey(key)
        except WindowsError:
            pass
            
    chrome_path = find_system_chrome()
    if chrome_path:
        try:
            cmd = f'(Get-Item "{chrome_path}").VersionInfo.ProductVersion'
            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version_str = result.stdout.strip()
                match = re.match(r'^(\d+)', version_str)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
            
    return None

def kill_chrome_by_profile(profile_path: str):
    """Tìm và tắt các tiến trình chrome.exe đang chiếm dụng profile chỉ định bằng PowerShell."""
    profile_name = os.path.basename(profile_path)
    if not profile_name:
        return
    powershell_cmd = (
        f'Get-CimInstance Win32_Process -Filter "name = \'chrome.exe\' and CommandLine like \'%{profile_name}%\'" | '
        f'ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}'
    )
    try:
        subprocess.run(
            ["powershell", "-Command", powershell_cmd],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        time.sleep(1)
    except Exception as e:
        logger.error(f"Lỗi khi giải phóng profile Chrome: {e}")

def cleanup_profile_locks(profile_path: str):
    """Xóa các file lock của Chrome trong thư mục profile để tránh bị treo khi khởi động."""
    if not os.path.exists(profile_path):
        return
    try:
        for item in os.listdir(profile_path):
            item_path = os.path.join(profile_path, item)
            if os.path.isfile(item_path):
                name_lower = item.lower()
                if "lock" in name_lower or "singleton" in name_lower:
                    try:
                        os.remove(item_path)
                        logger.info(f"🗑️ Đã xóa file lock: {item_path}")
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"Lỗi khi dọn dẹp file lock: {e}")

def open_google_login_browser(profile_path: str) -> bool:
    """
    Mở Chrome thật cài trên hệ thống để người dùng đăng nhập tài khoản Google (dùng Gemini) và Raphael AI.
    Mở qua subprocess giúp bypass 100% cơ chế chặn login của Google.
    """
    # Giải phóng profile trước khi mở để tránh gộp tab vào tiến trình cũ đang chạy ngầm
    kill_chrome_by_profile(profile_path)
    cleanup_profile_locks(profile_path)
    
    portable_chrome = os.path.join(BASE_DIR, "chrome_bin", "chrome.exe")
    if os.path.exists(portable_chrome):
        chrome_path = portable_chrome
        logger.info("👉 Sử dụng Chrome Portable đi kèm để đăng nhập.")
    else:
        chrome_path = find_system_chrome()
        
    if not chrome_path:
        logger.error("Không tìm thấy Google Chrome cài đặt trên hệ thống.")
        return False
        
    abs_profile_path = os.path.abspath(profile_path)
    os.makedirs(abs_profile_path, exist_ok=True)
    
    cmd = [
        chrome_path,
        f"--user-data-dir={abs_profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
        "https://gemini.google.com/app",
        "https://labs.google/fx/vi/tools/flow"
    ]
    
    try:
        process = subprocess.Popen(cmd)
        process.wait()
        return True
    except Exception as e:
        logger.error(f"Lỗi khi mở trình duyệt Chrome đăng nhập: {e}")
        return False

class BrowserAutomationController:
    """
    Quản lý luồng chạy Chrome bằng undetected-chromedriver để:
    1. Đăng nhập và phân tích SRT trên Gemini.
    2. Chuyển hướng sang Google Labs Flow và tạo ảnh bằng JS Injection.
    """
    GEMINI_URL = 'https://gemini.google.com/app'
    LABS_URL = 'https://labs.google/fx/vi/tools/flow'

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.driver = None
        self.log_callback = log_callback or (lambda msg: logger.info(msg))
        self._script_injected = False
        self.raphael_configured = False

    def log(self, msg: str):
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception:
                print(msg)
        else:
            logger.info(msg)

    def setup_browser(self, profile_path: str, headless: bool = False) -> bool:
        """Khởi chạy undetected-chromedriver sử dụng profile được chỉ định."""
        try:
            # Giải phóng profile trước khi mở để tránh xung đột file lock và gộp tab
            kill_chrome_by_profile(profile_path)
            cleanup_profile_locks(profile_path)
            
            self.log(f"🌐 Khởi động Chrome (Profile: {os.path.basename(profile_path)})...")
            options = uc.ChromeOptions()
            options.add_argument(f"--user-data-dir={profile_path}")
            
            # Tạo thư mục download tạm thời
            self.temp_download_dir = os.path.abspath(os.path.join(BASE_DIR, "temp_downloads"))
            if os.path.exists(self.temp_download_dir):
                try:
                    import shutil
                    shutil.rmtree(self.temp_download_dir)
                except Exception:
                    pass
            os.makedirs(self.temp_download_dir, exist_ok=True)
            
            # Cấu hình Chrome tự động tải xuống thư mục tạm
            prefs = {
                "download.default_directory": self.temp_download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            options.add_experimental_option("prefs", prefs)
            
            # Tự động nạp extension bypass captcha đã cấu hình sẵn
            ext_path = os.path.join(BASE_DIR, "extension")
            if os.path.exists(ext_path):
                options.add_argument(f"--load-extension={ext_path}")
                self.log("   🔑 Đã nạp Extension Captcha Bridge thành công.")
            else:
                self.log("   ⚠️ Không tìm thấy thư mục Extension Captcha Bridge.")
                
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--disable-background-mode')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-logging')
            options.add_argument('--log-level=3')
            options.add_argument('--lang=vi-VN')
            options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
            
            # Tối ưu hóa hiệu năng
            options.add_argument('--disable-features=CalculateNativeWinOcclusion')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-hang-monitor')
            options.add_argument('--mute-audio')
            options.add_argument(
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
            )

            # Kiểm tra xem có sử dụng Chrome Portable đi kèm dự án không
            chrome_bin_dir = os.path.join(BASE_DIR, "chrome_bin")
            portable_chrome = os.path.join(chrome_bin_dir, "chrome.exe")
            portable_driver = os.path.join(chrome_bin_dir, "chromedriver.exe")
            
            if os.path.exists(portable_chrome) and os.path.exists(portable_driver):
                self.log("   🚀 Phát hiện Chrome Portable đi kèm dự án. Sử dụng cấu hình offline độc lập hoàn toàn!")
                self.driver = uc.Chrome(
                    options=options,
                    browser_executable_path=portable_chrome,
                    driver_executable_path=portable_driver
                )
            else:
                major_version = get_chrome_major_version()
                if major_version:
                    self.log(f"   ℹ️ Phiên bản Chrome: {major_version}")
                    self.driver = uc.Chrome(options=options, version_main=major_version)
                else:
                    self.log("   ℹ️ Không tự động phát hiện được phiên bản Chrome, khởi chạy mặc định...")
                    self.driver = uc.Chrome(options=options)
            
            # Nạp script monkey-patch tự động bắt Token Google Labs Flow
            self._inject_labs_monkey_patch()
            
            self.headless = headless
            if headless:
                # Đẩy cửa sổ ra ngoài màn hình để ẩn mà không bị đóng băng tab (headless stealth)
                self.driver.set_window_position(-32000, -32000)
                self.driver.set_window_size(1280, 800)
                self.log('   🔒 Trình duyệt đang chạy ở chế độ ẩn nền.')
            else:
                self.driver.maximize_window()

            # Inject script stealth để ẩn WebDriver
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN','vi','en-US','en']});
                    Object.defineProperty(document, 'visibilityState', {get: () => 'visible', configurable: true});
                    Object.defineProperty(document, 'hidden', {get: () => false, configurable: true});
                    document.addEventListener('visibilitychange', function(e) {
                        e.stopImmediatePropagation();
                    }, true);
                    Document.prototype.hasFocus = function() { return true; };
                """
            })
            return True
        except Exception as e:
            self.log(f"❌ Lỗi khởi động trình duyệt: {e}")
            return False

    def connect_to_gemini(self) -> bool:
        """Truy cập Gemini và kiểm tra sẵn sàng."""
        try:
            self.log(f"🌐 Truy cập {self.GEMINI_URL}...")
            self.driver.get(self.GEMINI_URL)
            time.sleep(4)
            
            # Nếu đã vào thẳng trang chat và có sẵn ô chat, kết thúc luôn không làm gì thêm
            if self._find_chat_input():
                self.log('   ✅ Đăng nhập & kết nối tới Gemini thành công!')
                return True
                
            # Nếu chưa có ô chat, mới thử xử lý popups và click nút bắt đầu
            self.log("   ℹ️ Chưa thấy ô chat. Kiểm tra popups hoặc nút bắt đầu...")
            self._handle_gemini_popups()
            self._click_gemini_start_buttons()
            time.sleep(2)
            
            # Đợi load ô chatbox
            for attempt in range(15):
                # Dọn dẹp tab phụ nếu bị click nhầm mở ra
                self._clean_extra_tabs()
                
                current_url = self.driver.current_url
                if "one.google.com" in current_url or "plans" in current_url:
                    self.log(f"   ⚠️ Phát hiện bị chuyển hướng sang: {current_url}")
                    self.log("   🔄 Đang điều hướng lại về trang chat Gemini...")
                    self.driver.get(self.GEMINI_URL)
                    time.sleep(4)
                    self._handle_gemini_popups()
                    self._click_gemini_start_buttons()
                
                if self._find_chat_input():
                    self.log('   ✅ Đăng nhập & kết nối tới Gemini thành công!')
                    return True
                    
                # Thử click lại nút bắt đầu nếu vẫn kẹt
                if attempt > 0 and attempt % 3 == 0:
                    self._click_gemini_start_buttons()
                    self._handle_gemini_popups()
                    
                time.sleep(2)
            
            self.log(f"   ❌ Không tìm thấy ô nhập chat. URL hiện tại: {self.driver.current_url}")
            self.log('   💡 Gợi ý: Hãy nhấn nút "Đăng nhập Google" trên ứng dụng, đăng nhập tài khoản của bạn và ĐẢM BẢO bạn đã vào được đến giao diện chat của Gemini (gửi thử được tin nhắn) trước khi đóng Chrome.')
            return False
        except Exception as e:
            self.log(f"❌ Lỗi truy cập Gemini: {e}")
            return False

    def _click_gemini_start_buttons(self):
        """Tự động click các nút 'Trò chuyện với Gemini' hoặc link vào app nếu bị kẹt ở trang giới thiệu."""
        try:
            selectors = [
                "//a[contains(., 'Trò chuyện')]",
                "//a[contains(., 'Chat with Gemini')]",
                "//a[contains(., 'Use Gemini')]",
                "//button[contains(., 'Trò chuyện')]",
                "//button[contains(., 'Get started')]",
                "//button[contains(., 'Bắt đầu')]"
            ]
            for sel in selectors:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        # Tránh click nhầm vào các link nâng cấp (upgrade/plans)
                        el_text = (el.text or "").lower()
                        if el.is_displayed() and "upgrade" not in el_text and "nâng cấp" not in el_text:
                            self.driver.execute_script("arguments[0].click();", el)
                            time.sleep(1.5)
                            return
                except Exception:
                    pass
        except Exception:
            pass

    def _clean_extra_tabs(self):
        """Đóng toàn bộ các tab phụ đang bị mở thừa, chỉ giữ lại tab đầu tiên."""
        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                self.log(f"   🧹 Phát hiện {len(handles) - 1} tab phụ đang mở. Tiến hành đóng và quay về tab chính...")
                main_handle = handles[0]
                for handle in handles[1:]:
                    try:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                    except Exception:
                        pass
                self.driver.switch_to.window(main_handle)
                time.sleep(1)
        except Exception as e:
            self.log(f"   ⚠️ Lỗi dọn dẹp tab phụ: {e}")

    def _handle_gemini_popups(self):
        """Đồng ý các thông báo điều khoản ban đầu trên Gemini."""
        try:
            selectors = [
                "//button[contains(., 'Use Gemini')]",
                "//button[contains(., 'Đồng ý')]",
                "//button[contains(., 'Agree')]",
                "//button[contains(., 'I agree')]",
                "//button[contains(., 'Tôi đồng ý')]"
            ]
            for sel in selectors:
                try:
                    btns = self.driver.find_elements(By.XPATH, sel)
                    for btn in btns:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            time.sleep(1)
                except Exception:
                    pass
        except Exception:
            pass

    def _find_chat_input(self):
        """Tìm ô nhập chat editable của Gemini."""
        try:
            elems = self.driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true'], .ql-editor")
            if elems and elems[0].is_displayed():
                return elems[0]
            return None
        except Exception:
            return None

    def new_chat(self) -> bool:
        """Tạo phiên chat mới bằng cách reload trang và click nút 'Trò chuyện mới' (New chat) nếu có."""
        if not self.driver:
            return False
        try:
            self.log("💬 Khởi tạo cuộc trò chuyện mới trên Gemini...")
            self.driver.get(self.GEMINI_URL)
            time.sleep(4)
            
            # Thử click nút 'Trò chuyện mới' để đảm bảo sang phiên chat sạch
            selectors = [
                "//span[contains(text(), 'Trò chuyện mới')]",
                "//span[contains(text(), 'New chat')]",
                "//button[contains(., 'Trò chuyện mới')]",
                "//button[contains(., 'New chat')]",
                "//a[contains(@href, '/app')]"
            ]
            for sel in selectors:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed():
                            self.driver.execute_script("arguments[0].click();", el)
                            time.sleep(2)
                            break
                except Exception:
                    pass
            
            for _ in range(10):
                if self._find_chat_input():
                    return True
                time.sleep(1)
            return False
        except Exception as e:
            self.log(f"❌ Không thể tạo chat mới: {e}")
            return False

    def send_prompt_and_wait(self, prompt: str, timeout_sec: int = 180) -> str:
        """Gửi prompt và đợi Gemini phản hồi."""
        try:
            # Chờ Gemini rảnh (không có nút stop-icon hiển thị)
            for _ in range(20):
                stop_visible = self.driver.execute_script('''
                    const s = document.querySelector('button.send-button .stop-icon');
                    return s && !s.classList.contains('hidden');
                ''')
                if not stop_visible:
                    break
                time.sleep(1)

            prev_count = self._count_responses()

            # Nhập văn bản bằng clipboard (tránh lỗi gõ chữ tiếng Việt hoặc ký tự đặc biệt)
            editor = self._find_chat_input()
            if not editor:
                self.log('❌ Lỗi: Không thể tìm thấy khung chatbox.')
                return ''
                
            editor.click()
            time.sleep(0.2)
            
            # Xóa text cũ
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
            time.sleep(0.1)
            ActionChains(self.driver).send_keys(Keys.DELETE).perform()
            time.sleep(0.2)

            # Paste prompt
            pyperclip.copy(prompt)
            ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            time.sleep(0.5)

            # Click nút gửi
            self._submit_prompt()
            self.log('⏳ Chờ phân tích kịch bản từ Gemini...')
            return self._wait_for_response(prev_count, timeout_sec)
        except Exception as e:
            self.log(f"❌ Lỗi gửi prompt: {e}")
            return ''

    def _submit_prompt(self):
        send_selectors = [
            'button.send-button',
            'button[aria-label*="Send"]',
            'button[aria-label*="Gửi"]',
            'button[data-test-id="send-button"]',
        ]
        for sel in send_selectors:
            try:
                btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for btn in btns:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        return
            except Exception:
                pass
        try:
            editor = self._find_chat_input()
            if editor:
                editor.send_keys(Keys.ENTER)
        except Exception:
            pass

    def _count_responses(self) -> int:
        try:
            return self.driver.execute_script('''
                return document.querySelectorAll('model-response').length + document.querySelectorAll('pending-response').length;
            ''') or 0
        except Exception:
            return 0

    def _wait_for_response(self, prev_count: int, timeout_sec: int) -> str:
        start_time = time.time()
        last_logged = start_time
        while time.time() - start_time < timeout_sec:
            try:
                result = self.driver.execute_script('''
                    const mrs = document.querySelectorAll('model-response');
                    const prevCount = arguments[0];

                    if (mrs.length <= prevCount) {
                        return {state: 'waiting', text: ''};
                    }

                    const lastMR = mrs[mrs.length - 1];
                    const footer = lastMR.querySelector('.response-footer');
                    const footerComplete = footer ? footer.classList.contains('complete') : false;
                    const hasActions = !!lastMR.querySelector('message-actions');

                    let text = '';
                    const textSels = [
                        'message-content .markdown',
                        'structured-content-container .markdown',
                        '.model-response-text',
                        'message-content',
                    ];
                    
                    for (const sel of textSels) {
                        const md = lastMR.querySelector(sel);
                        if (md) {
                            const t = (md.innerText || md.textContent || '').trim();
                            if (t.length > 2) { text = t; break; }
                        }
                    }

                    if ((footerComplete || hasActions) && text.length > 5) {
                        return {state: 'complete', text: text};
                    }
                    if (text.length > 5) {
                        return {state: 'generating', text: text};
                    }
                    return {state: 'waiting', text: ''};
                ''', prev_count)

                state = result.get('state', 'waiting')
                text = result.get('text', '')

                if state == 'complete':
                    return text

                now = time.time()
                if now - last_logged >= 15:
                    self.log(f"   ⏳ Đang chờ câu trả lời ({int(now - start_time)}s)...")
                    last_logged = now
            except Exception:
                pass
            time.sleep(1)

        # Fallback lấy text khẩn cấp
        try:
            return self.driver.execute_script('''
                const mrs = document.querySelectorAll('model-response');
                if (mrs.length > 0) {
                    const last = mrs[mrs.length - 1];
                    const md = last.querySelector('message-content .markdown') || last.querySelector('message-content');
                    if (md) return (md.innerText || md.textContent || '').trim();
                }
                return '';
            ''')
        except Exception:
            return ''

    def analyze_srt(self, srt_content: str, n_keywords: int) -> List[Dict]:
        """Gửi nội dung SRT lên Gemini để phân tích và lấy JSON kết quả."""
        self.log(f"📝 Đang gửi phân tích phụ đề SRT ({n_keywords} từ khóa)...")
        prompt = (
            f"Dưới đây là nội dung tệp phụ đề SRT:\n\n{srt_content}\n\n"
            f"Nhiệm vụ: Hãy phân tích tệp SRT này, tìm ra các từ khóa quan trọng và mô tả các phân đoạn tương ứng. "
            f"Chọn ngẫu nhiên đúng {n_keywords} từ khóa xuất hiện trong tệp phụ đề. "
            f"Với mỗi từ khóa được chọn, hãy trích xuất đoạn Timeline (Start -> End) tương ứng của nó "
            f"và viết một câu Prompt tiếng Anh chi tiết để tạo ảnh mô tả cho đoạn chứa từ khóa đó. "
            f"Đặc biệt chú ý: định dạng timeline là HH:MM:SS (hoặc HH:MM:SS,mmm), hãy ghi lại chính xác thời gian bắt đầu và kết thúc của đoạn chứa từ khóa trong SRT.\n\n"
            f"Trả về kết quả duy nhất ở định dạng JSON thô bên dưới, không chứa bất kỳ lời giải thích nào khác ngoài chuỗi JSON:\n"
            f"[\n"
            f"  {{\"keyword\": \"từ khóa\", \"start\": \"HH:MM:SS\", \"end\": \"HH:MM:SS\", \"prompt\": \"câu prompt tiếng Anh chi tiết tạo ảnh\"}}\n"
            f"]"
        )
        
        response = self.send_prompt_and_wait(prompt)
        if not response:
            self.log("❌ Không nhận được câu trả lời từ Gemini.")
            return []
            
        self.log("✅ Đã nhận được phản hồi từ Gemini. Tiến hành trích xuất dữ liệu JSON...")
        
        # Regex trích xuất JSON
        json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
        if not json_match:
            # Fallback thử tìm block ```json ... ```
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            
        json_str = json_match.group(0) if json_match else response
        if json_match and len(json_match.groups()) > 0 and '```' in response:
            json_str = json_match.group(1)

        try:
            # Làm sạch chuỗi JSON nếu có tạp chất
            json_str = json_str.strip()
            # Bỏ ký tự ``` hoặc ```json ở đầu/cuối nếu có
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()
            
            data = json.loads(json_str)
            self.log(f"✅ Đã phân tích thành công JSON: Tìm thấy {len(data)} từ khóa.")
            return data
        except Exception as e:
            self.log(f"❌ Không thể parse dữ liệu JSON từ phản hồi: {e}")
            self.log(f"Nội dung phản hồi thô: {response[:300]}...")
            return []

    # ──── RAPHAEL AI METHODS ────

    def navigate_to_raphael(self) -> bool:
        """Chuyển hướng trình duyệt sang Raphael.app và chuẩn bị tạo ảnh."""
        try:
            self.log("🌐 Đang chuyển hướng sang Raphael AI: https://raphael.app/vi...")
            self.driver.get("https://raphael.app/vi")
            time.sleep(5)

            # Kiểm tra trạng thái đăng nhập của người dùng trên Raphael AI
            self.log("🔍 Kiểm tra trạng thái đăng nhập tài khoản...")
            has_login_btn = self.driver.execute_script("""
                const elements = Array.from(document.querySelectorAll('a, button, div, span'));
                const btn = elements.find(el => {
                    const text = (el.innerText || el.textContent || "").trim();
                    return (text === 'Đăng nhập' || text === 'Sign in') && el.offsetParent !== null;
                });
                return !!btn;
            """)
            
            # Nếu tìm thấy nút Đăng nhập đang hiển thị, khuyến nghị đăng nhập nhưng không bắt buộc
            if has_login_btn:
                self.log("⚠️ Tài khoản chưa đăng nhập trên Raphael AI.")
                self.log("👉 Bạn có thể đăng nhập (bằng Google/Email) trên cửa sổ Chrome để tăng lượt tạo.")
                self.log("⏳ Chờ 10s nếu bạn muốn đăng nhập, sau đó chương trình sẽ tự động tiếp tục...")
                
                logged_in = False
                for i in range(4): # 4 * 2.5 = 10 giây
                    time.sleep(2.5)
                    # Kiểm tra lại nút đăng nhập
                    current_has_btn = self.driver.execute_script("""
                        const elements = Array.from(document.querySelectorAll('a, button, div, span'));
                        const btn = elements.find(el => {
                            const text = (el.innerText || el.textContent || "").trim();
                            return (text === 'Đăng nhập' || text === 'Sign in') && el.offsetParent !== null;
                        });
                        return !!btn;
                    """)
                    if not current_has_btn:
                        self.log("✅ Đăng nhập thành công! Tiếp tục quy trình...")
                        logged_in = True
                        break
                
                if not logged_in:
                    self.log("ℹ️ Tiếp tục chạy với tư cách tài khoản ẩn danh (Anonymous)...")
            else:
                self.log("✅ Đã đăng nhập tài khoản.")

            self._script_injected = True
            self.raphael_configured = False
            return True
        except Exception as e:
            self.log(f"❌ Lỗi thiết lập Raphael AI: {e}")
            return False

    def configure_raphael_settings(self):
        """Cấu hình các thiết lập của Raphael AI một lần duy nhất để tối ưu tốc độ."""
        try:
            self.log("⚙️ Đang cấu hình các thiết lập Raphael AI (Model 2.0, Tắt Chế độ Nhanh, Tỷ lệ 16:9, Số lượng ảnh 1)...")
            
            # 1. Đảm bảo sử dụng model 0 tín dụng (Raphael 2.0)
            self.log("   🤖 Đang thiết lập model 0 tín dụng (Raphael 2.0)...")
            self.driver.execute_script("""
                try {
                    const elements = Array.from(document.querySelectorAll('div, button, span'));
                    const currentModelText = elements.find(el => {
                        const text = (el.innerText || el.textContent || "").trim();
                        return (text.includes('Raphael 2.0') || text === 'Raphael 2.0') && el.offsetParent !== null;
                    });
                    
                    if (!currentModelText) {
                        const modelDropdownBtn = elements.find(el => {
                            const text = (el.innerText || el.textContent || "").trim();
                            return (text.includes('Raphael Pro') || text.includes('Flux') || text.includes('PixArt') || text.includes('Model:') || text.includes('Raphael 2.0') || text.includes('Raphael Basic')) && el.offsetParent !== null;
                        });
                        if (modelDropdownBtn) {
                            modelDropdownBtn.click();
                            setTimeout(() => {
                                const menuEls = Array.from(document.querySelectorAll('div, span, button, p, li'));
                                const basicOption = menuEls.find(el => {
                                    const text = (el.innerText || el.textContent || "").trim();
                                    return (text.includes('Raphael 2.0') || text === 'Raphael 2.0') && el.offsetParent !== null;
                                });
                                if (basicOption) basicOption.click();
                            }, 500);
                        }
                    }
                } catch(e) {}
            """)
            time.sleep(1.5)
            
            # 2. Tắt Chế độ Nhanh để tránh bị trừ tín dụng
            self.log("   ⚡ Đang tắt Chế độ Nhanh để tránh bị trừ tín dụng...")
            self.driver.execute_script("""
                try {
                    const switchBtns = Array.from(document.querySelectorAll('button[role="switch"]'));
                    const fastModeSwitch = switchBtns.find(btn => {
                        const parent = btn.parentElement;
                        if (!parent) return false;
                        const parentText = (parent.innerText || parent.textContent || "").trim();
                        return parentText.includes('Chế độ Nhanh') || parentText.includes('Fast Mode');
                    });
                    
                    if (fastModeSwitch) {
                        const isChecked = fastModeSwitch.getAttribute('aria-checked') === 'true';
                        if (isChecked) {
                            fastModeSwitch.click();
                        }
                    }
                } catch(e) {}
            """)
            time.sleep(1.0)
            
            # 3. Mở popup cài đặt và cấu hình tỷ lệ + số lượng ảnh
            self.log("   📐 Đang mở cài đặt tỷ lệ và số lượng ảnh...")
            self.driver.execute_script("""
                try {
                    const elements = Array.from(document.querySelectorAll('div, span, button'));
                    const ratioBtn = elements.find(el => {
                        const text = (el.innerText || el.textContent || "").trim();
                        return (text === '1:1' || text === '16:9' || text === '9:16' || text === '4:3' || text === '3:2') && el.offsetParent !== null;
                    });
                    if (ratioBtn) {
                        ratioBtn.click();
                    }
                } catch(e) {}
            """)
            time.sleep(1.0) # Đợi popup mở ra
            
            self.log("   📐 Thiết lập tỷ lệ 16:9 và số lượng ảnh 1 trong cài đặt...")
            self.driver.execute_script("""
                try {
                    // Chọn tỷ lệ 16:9
                    const popupEls = Array.from(document.querySelectorAll('div, span, button, p, li'));
                    const option169 = popupEls.find(el => {
                        const text = (el.innerText || el.textContent || "").trim();
                        return text === '16:9' && el.offsetParent !== null;
                    });
                    if (option169) option169.click();
                } catch(e) {}
            """)
            time.sleep(0.5)
            
            self.driver.execute_script("""
                try {
                    // Chọn số lượng ảnh là 1
                    const labels = Array.from(document.querySelectorAll('div, span, p, label'));
                    const qtyLabel = labels.find(el => {
                        const text = (el.innerText || el.textContent || "").trim().toLowerCase();
                        return text.includes('số lượng đầu ra') || text.includes('số lượng') || text.includes('number of images') || text.includes('output quantity');
                    });
                    if (qtyLabel) {
                        let parent = qtyLabel.parentElement;
                        for (let i = 0; i < 3; i++) {
                            if (!parent) break;
                            const btns = Array.from(parent.querySelectorAll('button'));
                            const btn1 = btns.find(b => (b.innerText || b.textContent || "").trim() === '1');
                            if (btn1) {
                                btn1.click();
                                break;
                            }
                            parent = parent.parentElement;
                        }
                    }
                } catch(e) {}
            """)
            time.sleep(1.0)
            
            # Đóng popup cài đặt
            self.driver.execute_script("""
                try {
                    const elements = Array.from(document.querySelectorAll('div, span, button'));
                    const ratioBtn = elements.find(el => {
                        const text = (el.innerText || el.textContent || "").trim();
                        return (text === '1:1' || text === '16:9' || text === '9:16' || text === '4:3' || text === '3:2') && el.offsetParent !== null;
                    });
                    if (ratioBtn) {
                        ratioBtn.click();
                    }
                } catch(e) {}
            """)
            time.sleep(1.0)
            
            self.raphael_configured = True
            self.log("✅ Cấu hình các thiết lập Raphael AI hoàn tất!")
        except Exception as e:
            self.log(f"⚠️ Lỗi cấu hình cài đặt Raphael AI: {e}")

    def generate_image_by_raphael(self, prompt: str, aspect_ratio: str = 'IMAGE_ASPECT_RATIO_LANDSCAPE', model: str = 'GEM_PIX_2') -> Optional[str]:
        """
        Thực hiện sinh ảnh bằng Raphael AI hoàn toàn qua cơ chế UI Automation an toàn,
        mô phỏng hành vi người dùng thật để bypass WAF/Cloudflare.
        """
        try:
            self.log(f"🎨 Bắt đầu sinh ảnh cho prompt: '{prompt[:60]}...'")
            
            # Đảm bảo cấu hình Raphael AI đã được thiết lập (chỉ làm một lần)
            if not getattr(self, 'raphael_configured', False):
                self.configure_raphael_settings()
            
            # --- CƠ CHẾ SINH ẢNH: UI AUTOMATION (MÔ PHỎNG HÀNH VI NGƯỜI DÙNG AN TOÀN) ---
            self.log("   ⌨️ Đang điền prompt vào ô chat trên giao diện...")
            
            # Ghi nhận số lượng ảnh hiện có (chuẩn hóa thành URL tuyệt đối)
            old_srcs = self.driver.execute_script("""
                const srcs = [];
                document.querySelectorAll('img').forEach(img => { 
                    let src = img.src || "";
                    if (src) {
                        if (src.startsWith('/')) {
                            src = window.location.origin + src;
                        }
                        srcs.push(src); 
                    }
                });
                return srcs;
            """)
            self.log(f"   📊 Số lượng ảnh hiện có trên trang: {len(old_srcs)}")

            # Ghi nhận các file hiện có trong thư mục download để phát hiện file mới tải về
            download_dirs = []
            if hasattr(self, 'temp_download_dir') and os.path.exists(self.temp_download_dir):
                download_dirs.append(self.temp_download_dir)
            win_download = get_windows_download_path()
            if os.path.exists(win_download):
                download_dirs.append(win_download)
                
            old_files = {}
            for d in download_dirs:
                if os.path.exists(d):
                    try:
                        old_files[d] = set(os.listdir(d))
                    except Exception:
                        old_files[d] = set()
            
            # Điền text qua React Tracker Bypass
            input_ok = self.driver.execute_script(f"""
                try {{
                    const el = document.getElementById('image-generator-prompt');
                    if (el) {{
                        el.focus();
                        const lastValue = el.value;
                        el.value = {prompt!r};
                        if (el._valueTracker) el._valueTracker.setValue(lastValue);
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }} catch(e) {{
                    return false;
                }}
            """)
            
            if not input_ok:
                self.log("   ❌ Không tìm thấy ô nhập prompt trên UI.")
                return None
                
            time.sleep(1.0)
            
            # Click nút Tạo trên UI
            self.log("   🖱️ Đang click nút 'Tạo' trên giao diện...")
            clicked = self.driver.execute_script("""
                try {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const btn = buttons.find(b => {
                        const text = (b.innerText || b.textContent || "").trim();
                        return text === 'Tạo' || text === 'Generate' || text.includes('Tạo') || text.includes('Generate');
                    });
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    return false;
                } catch(e) {
                    return false;
                }
            """)
            
            if clicked:
                self.log("   ✅ Đã click nút Tạo.")
            else:
                self.log("   ⚠️ Không click được nút Tạo qua JS. Thử nhấn phím Enter...")
                try:
                    el = self.driver.find_element(By.ID, 'image-generator-prompt')
                    el.send_keys(Keys.ENTER)
                    self.log("   ✅ Đã gửi phím Enter.")
                except Exception:
                    pass
            
            # Chờ ảnh mới xuất hiện trong gallery
            self.log("   ⏳ Đang chờ ảnh mới được tạo ra trên UI (Max 90s)...")
            start_time = time.time()
            timeout = 90
            while time.time() - start_time < timeout:
                # 1. Kiểm tra xem có Cloudflare Turnstile Captcha không
                is_turnstile = self.driver.execute_script("""
                    const iframes = Array.from(document.querySelectorAll('iframe'));
                    const hasIframe = iframes.some(iframe => {
                        const src = iframe.src || "";
                        return src.includes('challenges.cloudflare.com') && iframe.offsetParent !== null;
                    });
                    const elements = Array.from(document.querySelectorAll('div, section, p, span'));
                    const hasText = elements.some(el => {
                        if (el.offsetParent === null) return false;
                        const text = (el.innerText || el.textContent || "").toLowerCase();
                        return text.includes('hoàn tất xác minh') || text.includes('verify you are human');
                    });
                    return hasIframe || hasText;
                """)
                
                if is_turnstile:
                    self.log("   ⚠️ Phát hiện Cloudflare Turnstile Captcha (Verify you are human)!")
                    if hasattr(self, 'headless') and self.headless:
                        self.log("   🖥️ Tự động hiển thị trình duyệt Chrome lên màn hình để bạn giải captcha...")
                        try:
                            self.driver.set_window_position(100, 100)
                            self.driver.maximize_window()
                        except Exception:
                            pass
                    self.log("   👉 VUI LÒNG CLICK CHỌN ô 'Verify you are human' trên trình duyệt để tiếp tục.")
                    self.log("   ⏳ Đang chờ giải captcha (Chờ tối đa 60s)...")
                    
                    captcha_resolved = False
                    for j in range(30): # 30 * 2 = 60s
                        time.sleep(2)
                        still_turnstile = self.driver.execute_script("""
                            const iframes = Array.from(document.querySelectorAll('iframe'));
                            const hasIframe = iframes.some(iframe => {
                                const src = iframe.src || "";
                                return src.includes('challenges.cloudflare.com') && iframe.offsetParent !== null;
                            });
                            const elements = Array.from(document.querySelectorAll('div, section, p, span'));
                            const hasText = elements.some(el => {
                                if (el.offsetParent === null) return false;
                                const text = (el.innerText || el.textContent || "").toLowerCase();
                                return text.includes('hoàn tất xác minh') || text.includes('verify you are human');
                            });
                            return hasIframe || hasText;
                        """)
                        if not still_turnstile:
                            self.log("   ✅ Giải captcha thành công! Tiếp tục chờ ảnh...")
                            if hasattr(self, 'headless') and self.headless:
                                self.log("   🔒 Đang ẩn trình duyệt Chrome trở lại chế độ chạy ngầm...")
                                try:
                                    self.driver.set_window_position(-32000, -32000)
                                except Exception:
                                    pass
                            captcha_resolved = True
                            start_time = time.time() # Reset thời gian chờ
                            break
                    if not captcha_resolved:
                        self.log("   ❌ Quá thời gian chờ giải captcha. Dừng tạo ảnh.")
                        if hasattr(self, 'headless') and self.headless:
                            try:
                                self.driver.set_window_position(-32000, -32000)
                            except Exception:
                                pass
                        return None
                        
                # 2. Kiểm tra xem có popup chặn/yêu cầu đăng nhập/giới hạn lượt không
                is_blocked = self.driver.execute_script("""
                    const dialogs = Array.from(document.querySelectorAll('div, section, [role="dialog"]'));
                    const blockedKeywords = ['đăng nhập', 'sign in', 'login', 'giới hạn', 'limit', 'nâng cấp', 'upgrade', 'hết lượt'];
                    const popup = dialogs.find(el => {
                        if (el.offsetParent === null) return false;
                        const style = window.getComputedStyle(el);
                        const zIndex = parseInt(style.zIndex);
                        if (isNaN(zIndex) || zIndex < 10) return false;
                        const text = (el.innerText || el.textContent || "").toLowerCase();
                        return blockedKeywords.some(kw => text.includes(kw));
                    });
                    return !!popup;
                """)
                
                if is_blocked:
                    self.log("   ⚠️ Phát hiện popup yêu cầu đăng nhập hoặc hết lượt tạo ẩn danh!")
                    if hasattr(self, 'headless') and self.headless:
                        self.log("   🖥️ Tự động hiển thị trình duyệt Chrome lên màn hình để bạn đăng nhập...")
                        try:
                            self.driver.set_window_position(100, 100)
                            self.driver.maximize_window()
                        except Exception:
                            pass
                    self.log("   👉 Vui lòng đăng nhập tài khoản của bạn ngay trên cửa sổ Chrome để tiếp tục.")
                    self.log("   ⏳ Đang chờ bạn đăng nhập và giải phóng popup (Chờ tối đa 60s)...")
                    
                    resolved = False
                    for j in range(20): # 20 * 3 = 60s
                        time.sleep(3)
                        still_blocked = self.driver.execute_script("""
                            const dialogs = Array.from(document.querySelectorAll('div, section, [role="dialog"]'));
                            const blockedKeywords = ['đăng nhập', 'sign in', 'login', 'giới hạn', 'limit', 'nâng cấp', 'upgrade', 'hết lượt'];
                            const popup = dialogs.find(el => {
                                if (el.offsetParent === null) return false;
                                const style = window.getComputedStyle(el);
                                const zIndex = parseInt(style.zIndex);
                                if (isNaN(zIndex) || zIndex < 10) return false;
                                const text = (el.innerText || el.textContent || "").toLowerCase();
                                return blockedKeywords.some(kw => text.includes(kw));
                            });
                            return !!popup;
                        """)
                        if not still_blocked:
                            self.log("   ✅ Đã giải phóng popup đăng nhập! Thiết lập model 0 tín dụng (Raphael 2.0) và chuyển tỷ lệ sang 16:9...")
                            if hasattr(self, 'headless') and self.headless:
                                self.log("   🔒 Đang ẩn trình duyệt Chrome trở lại chế độ chạy ngầm...")
                                try:
                                    self.driver.set_window_position(-32000, -32000)
                                except Exception:
                                    pass
                            # Gọi hàm cấu hình lại cài đặt Raphael AI
                            self.configure_raphael_settings()
                            # Click Tạo
                            self.driver.execute_script("""
                                try {
                                    const buttons = Array.from(document.querySelectorAll('button'));
                                    const btn = buttons.find(b => {
                                        const text = (b.innerText || b.textContent || "").trim();
                                        return text.includes('Tạo') || text.includes('Generate');
                                    });
                                    if (btn) btn.click();
                                } catch(e) {}
                            """)
                            resolved = True
                            # Reset thời gian bắt đầu chờ ảnh để tránh bị timeout ngay lập tức
                            start_time = time.time()
                            break
                    if not resolved:
                        self.log("   ❌ Quá thời gian chờ đăng nhập giải phóng popup. Dừng tạo ảnh.")
                        if hasattr(self, 'headless') and self.headless:
                            try:
                                self.driver.set_window_position(-32000, -32000)
                            except Exception:
                                pass
                        return None

                # 2. Tìm ảnh mới và thử click nút Tải xuống của nó trên UI
                download_clicked_data = self.driver.execute_script(f"""
                    const oldSrcs = {json.dumps(old_srcs)};
                    const imgs = Array.from(document.querySelectorAll('img'));
                    const newImg = imgs.find(img => {{
                        let src = img.src || "";
                        const attrSrc = img.getAttribute('src') || "";
                        
                        // Nhận diện cả đường dẫn tương đối bắt đầu bằng "/"
                        if (!src.startsWith('http') && !src.startsWith('blob:')) {{
                            if (attrSrc.startsWith('/') || attrSrc.startsWith('http') || attrSrc.startsWith('blob:')) {{
                                src = attrSrc;
                            }} else {{
                                return false;
                            }}
                        }}
                        
                        if (src.includes('avatar') || src.includes('logo') || src.includes('googleusercontent') || src.includes('captcha')) return false;
                        
                        // Chuẩn hóa thành URL tuyệt đối để so sánh chính xác với oldSrcs
                        let absSrc = src;
                        if (src.startsWith('/')) {{
                            absSrc = window.location.origin + src;
                        }}
                        
                        return !oldSrcs.includes(absSrc) && !oldSrcs.includes(src);
                    }});
                    
                    if (newImg && newImg.complete && newImg.naturalWidth > 0) {{
                        let finalSrc = newImg.src || "";
                        if (finalSrc.startsWith('/')) {{
                            finalSrc = window.location.origin + finalSrc;
                        }}
                        
                        // Tìm nút Tải xuống gần newImg nhất
                        let parent = newImg.parentElement;
                        let downloadBtn = null;
                        for (let i = 0; i < 4; i++) {{
                            if (!parent) break;
                            downloadBtn = parent.querySelector('button[aria-label="Tải xuống"]') || 
                                          parent.querySelector('button[aria-label*="download"]') ||
                                          Array.from(parent.querySelectorAll('button')).find(btn => btn.querySelector('svg.lucide-download'));
                            if (downloadBtn) break;
                            parent = parent.parentElement;
                        }}
                        
                        if (downloadBtn) {{
                            downloadBtn.click();
                            return {{ success: true, src: finalSrc }};
                        }}
                        return {{ success: false, src: finalSrc, error: 'Không tìm thấy nút Tải xuống' }};
                    }}
                    return null;
                """)
                
                if download_clicked_data:
                    img_url = download_clicked_data.get('src')
                    self.log(f"   🎯 Tìm thấy ảnh mới trên UI: {img_url}")
                    
                    if download_clicked_data.get('success'):
                        self.log("   🖱️ Đã click nút Tải xuống trên giao diện. Đang chờ file tải về...")
                        
                        # Chờ file tải về (Max 15s)
                        file_found = None
                        file_dir = None
                        start_dl_time = time.time()
                        
                        while time.time() - start_dl_time < 15:
                            for d in download_dirs:
                                if not os.path.exists(d):
                                    continue
                                try:
                                    current_files = set(os.listdir(d))
                                    new_files = current_files - old_files.get(d, set())
                                    valid_new_files = [f for f in new_files if not f.endswith('.crdownload') and not f.endswith('.tmp')]
                                    if valid_new_files:
                                        file_found = valid_new_files[0]
                                        file_dir = d
                                        break
                                except Exception:
                                    pass
                            if file_found:
                                break
                            time.sleep(0.5)
                            
                        if file_found:
                            file_path = os.path.join(file_dir, file_found)
                            self.log(f"   💾 Đã phát hiện file ảnh tải về: {file_path}")
                            
                            # Đợi file tải xong hoàn toàn (size không đổi trong 0.5s)
                            last_size = -1
                            for _ in range(10):
                                try:
                                    current_size = os.path.getsize(file_path)
                                    if current_size > 0 and current_size == last_size:
                                        break
                                    last_size = current_size
                                except Exception:
                                    pass
                                time.sleep(0.3)
                                
                            # Đọc file và convert sang Base64
                            try:
                                with open(file_path, "rb") as f:
                                    b64 = base64.b64encode(f.read()).decode('utf-8')
                                
                                # Nếu file nằm trong thư mục tạm của chúng ta, xóa đi để dọn dẹp
                                if hasattr(self, 'temp_download_dir') and file_dir == self.temp_download_dir:
                                    try:
                                        os.remove(file_path)
                                    except Exception:
                                        pass
                                        
                                self.log("   ✅ Tải ảnh và đọc file thành công!")
                                return b64
                            except Exception as read_err:
                                self.log(f"   ⚠️ Lỗi đọc file ảnh tải về: {read_err}")
                        else:
                            self.log("   ⚠️ Không tìm thấy file mới tải về trong thời gian chờ.")
                    else:
                        self.log(f"   ⚠️ Không click được nút Tải xuống trên UI (Lỗi: {download_clicked_data.get('error')})")
                        
                    # ─── FALLBACK: Nếu click tải xuống thất bại hoặc không tìm thấy file tải về ───
                    self.log("   🔄 Chuyển sang phương án fallback (Canvas / fetch / requests)...")
                    
                    # Thử lấy Base64 bằng Canvas trước
                    canvas_b64 = self.driver.execute_script(f"""
                        const imgs = Array.from(document.querySelectorAll('img'));
                        const newImg = imgs.find(img => {{
                            let src = img.src || "";
                            if (src.includes('{img_url}') || (img.getAttribute('src') && img.getAttribute('src').includes('{img_url}'))) {{
                                return true;
                            }}
                            return false;
                        }});
                        if (newImg && newImg.complete && newImg.naturalWidth > 0) {{
                            try {{
                                const canvas = document.createElement('canvas');
                                canvas.width = newImg.naturalWidth;
                                canvas.height = newImg.naturalHeight;
                                const ctx = canvas.getContext('2d');
                                ctx.drawImage(newImg, 0, 0);
                                return {{ success: true, base64: canvas.toDataURL('image/png').split(',')[1] }};
                            }} catch(e) {{
                                return {{ success: false, error: e.toString() }};
                            }}
                        }}
                        return null;
                    """)
                    
                    if canvas_b64 and canvas_b64.get('success'):
                        b64 = canvas_b64.get('base64')
                        if b64 and len(b64) > 100:
                            self.log("   ✅ Fallback: Tải ảnh bằng Canvas thành công!")
                            return b64
                            
                    # Nếu Canvas lỗi, thử fetch/requests như cũ
                    self.log(f"   ⚠️ Canvas fallback thất bại (Lỗi: {canvas_b64.get('error') if canvas_b64 else 'Không tìm thấy ảnh'}). Thử fetch browser...")
                    
                    if img_url.startswith('blob:'):
                        self.log("   🔄 Đang chuyển đổi ảnh blob sang Base64 bằng fetch trong browser...")
                        b64 = self.driver.execute_async_script("""
                            const callback = arguments[arguments.length - 1];
                            const blobUrl = arguments[0];
                            fetch(blobUrl)
                                .then(res => res.blob())
                                .then(blob => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => callback(reader.result.split(',')[1]);
                                    reader.readAsDataURL(blob);
                                })
                                .catch(err => callback(null));
                        """, img_url)
                        if b64:
                            self.log("   ✅ Fallback: Tải ảnh blob thành công!")
                            return b64
                    else:
                        # Thử tải ảnh trực tiếp bằng fetch trong browser trước để bypass Cloudflare
                        self.log("   🔄 Đang tải ảnh trực tiếp bằng fetch trong browser để bypass Cloudflare...")
                        b64 = self.driver.execute_async_script("""
                            const callback = arguments[arguments.length - 1];
                            const url = arguments[0];
                            fetch(url)
                                .then(res => res.blob())
                                .then(blob => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => callback(reader.result.split(',')[1]);
                                    reader.readAsDataURL(blob);
                                })
                                .catch(err => callback(null));
                        """, img_url)
                        if b64:
                            self.log("   ✅ Fallback: Tải ảnh URL bằng fetch browser thành công!")
                            return b64
                            
                        # Fallback cuối cùng bằng requests trong Python
                        self.log("   🔄 Đang tải ảnh trực tiếp từ URL bằng Python...")
                        try:
                            import requests
                            headers = {
                                "User-Agent": self.driver.execute_script("return navigator.userAgent;"),
                                "Referer": self.driver.current_url
                            }
                            res = requests.get(img_url, headers=headers, timeout=15)
                            if res.status_code == 200:
                                b64 = base64.b64encode(res.content).decode('utf-8')
                                self.log("   ✅ Fallback: Tải ảnh bằng Python requests thành công!")
                                return b64
                            else:
                                self.log(f"   ⚠️ Fallback: Tải ảnh bằng Python requests thất bại (HTTP {res.status_code})")
                        except Exception as req_err:
                            self.log(f"   ⚠️ Fallback: Lỗi tải ảnh bằng Python requests: {req_err}")
                time.sleep(2)
                
            self.log("   ❌ Quá thời gian chờ tạo ảnh trên UI (Timeout 90s).")
            try:
                self.driver.save_screenshot("screenshot_error_timeout.png")
            except Exception:
                pass
            return None
        except Exception as e:
            self.log(f"❌ Lỗi trong quá trình sinh ảnh: {e}")
            try:
                self.driver.save_screenshot("screenshot_error_exception.png")
            except Exception:
                pass
            return None

    def _simulate_human_behavior(self):
        """Mô phỏng hành vi di chuột và cuộn trang của người dùng để cải thiện reCAPTCHA score."""
        try:
            import random
            self.log("   🤖 Đang giả lập hành vi người dùng (di chuột, cuộn trang) để tối ưu điểm reCAPTCHA...")
            # 1. Di chuyển chuột ngẫu nhiên
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                window_size = self.driver.get_window_size()
                width = window_size.get('width', 1280)
                height = window_size.get('height', 800)
                
                for _ in range(random.randint(3, 5)):
                    x = random.randint(100, width - 100)
                    y = random.randint(100, height - 100)
                    actions.move_by_offset(x - width // 2, y - height // 2).perform()
                    time.sleep(random.uniform(0.2, 0.5))
                    actions.reset_actions()
            except Exception as e:
                pass

            # 2. Cuộn trang ngẫu nhiên
            try:
                for _ in range(random.randint(2, 4)):
                    scroll_amount = random.randint(100, 250)
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                    time.sleep(random.uniform(0.4, 0.8))
                    if random.random() > 0.7:
                        self.driver.execute_script(f"window.scrollBy(0, -{random.randint(50, 100)});")
                        time.sleep(random.uniform(0.3, 0.6))
            except Exception as e:
                pass

            # 3. Đợi reCAPTCHA ghi nhận telemetry
            wait_time = random.uniform(2.0, 3.5)
            time.sleep(wait_time)
        except Exception as e:
            self.log(f"   ⚠️ Lỗi mô phỏng hành vi: {e}")

    def get_recaptcha_token_from_driver(self, action: str = 'CHAT_GENERATION') -> Optional[str]:
        """Tự động sinh reCAPTCHA token trực tiếp bằng Selenium driver hiện tại."""
        try:
            # Chạy giả lập hành vi trước
            self._simulate_human_behavior()
            
            # Đợi grecaptcha.enterprise có sẵn trên trang
            self.log("   ⏳ Đợi grecaptcha.enterprise sẵn sàng...")
            ready = False
            for _ in range(10):
                try:
                    ready = self.driver.execute_script("""
                        return typeof window.grecaptcha !== 'undefined' && 
                               typeof window.grecaptcha.enterprise !== 'undefined' &&
                               typeof window.grecaptcha.enterprise.execute === 'function';
                    """)
                    if ready:
                        break
                except Exception:
                    pass
                time.sleep(1)
            
            if not ready:
                self.log("   ❌ grecaptcha.enterprise chưa sẵn sàng trên trang")
                return None
                
            # Lấy site key từ trang hoặc dùng mặc định
            site_key = self.driver.execute_script("""
                const badge = document.querySelector('.grecaptcha-badge');
                if (badge) {
                    const iframe = badge.querySelector('iframe[title="reCAPTCHA"]');
                    if (iframe) {
                        const src = iframe.getAttribute('src');
                        const match = src ? src.match(/[?&]k=([^&"']+)/) : null;
                        if (match) return decodeURIComponent(match[1]);
                    }
                }
                return '6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV'; // fallback site key
            """)
            
            self.log(f"   🚀 Gọi grecaptcha.enterprise.execute (action: {action})...")
            token_data = self.driver.execute_async_script(f"""
                const callback = arguments[arguments.length - 1];
                const siteKey = '{site_key}';
                const actionName = '{action}';
                
                const timeoutId = setTimeout(() => {{
                    callback({{ success: false, error: 'Timeout' }});
                }}, 25000);
                
                window.grecaptcha.enterprise.execute(siteKey, {{ action: actionName }})
                    .then(token => {{
                        clearTimeout(timeoutId);
                        callback({{ success: true, token: token }});
                    }})
                    .catch(err => {{
                        clearTimeout(timeoutId);
                        callback({{ success: false, error: err.toString() }});
                    }});
            """)
            
            if isinstance(token_data, dict) and token_data.get('success'):
                token = token_data.get('token')
                if token and len(token) > 100:
                    return token
                else:
                    self.log("   ⚠️ Token trả về rỗng hoặc quá ngắn")
            else:
                self.log(f"   ❌ Lỗi grecaptcha execute: {token_data.get('error') if token_data else 'unknown'}")
            return None
        except Exception as e:
            self.log(f"   ⚠️ Lỗi lấy reCAPTCHA từ driver: {e}")
            return None

    def _recover_from_recaptcha(self):
        """Tự động khôi phục và reset trạng thái reCAPTCHA."""
        try:
            self.log("   🔄 Đang phục hồi reCAPTCHA block. Điều hướng sang google.com và thiết lập lại Labs Flow...")
            self.driver.get('https://www.google.com')
            time.sleep(5)
            # Khởi tạo lại hoàn toàn Labs Flow
            self.navigate_to_labs_flow()
        except Exception as e:
            self.log(f"   ⚠️ Lỗi phục hồi reCAPTCHA: {e}")

    def _inject_labs_monkey_patch(self):
        """Tiêm script Page.addScriptToEvaluateOnNewDocument để tự động bắt Google Auth Token và Headers."""
        script = """
        (function() {
            window.__google_auth_token = null;
            window.__google_headers = {};
            
            // Monkey patch fetch
            const originalFetch = window.fetch;
            window.fetch = async function(...args) {
                const url = args[0];
                const options = args[1];
                if (options && options.headers) {
                    let auth = null;
                    if (options.headers instanceof Headers) {
                        auth = options.headers.get('authorization');
                    } else {
                        auth = options.headers['Authorization'] || options.headers['authorization'];
                    }
                    if (auth && auth.startsWith('Bearer ')) {
                        window.__google_auth_token = auth.substring(7);
                        if (options.headers instanceof Headers) {
                            for (let [k, v] of options.headers.entries()) {
                                window.__google_headers[k.toLowerCase()] = v;
                            }
                        } else {
                            for (let k in options.headers) {
                                window.__google_headers[k.toLowerCase()] = options.headers[k];
                            }
                        }
                    }
                }
                return originalFetch.apply(this, args);
            };
            
            // Monkey patch XMLHttpRequest
            const originalOpen = XMLHttpRequest.prototype.open;
            const originalSend = XMLHttpRequest.prototype.send;
            const originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
            
            XMLHttpRequest.prototype.open = function(...args) {
                this._headers = {};
                return originalOpen.apply(this, args);
            };
            
            XMLHttpRequest.prototype.setRequestHeader = function(header, value) {
                this._headers[header.toLowerCase()] = value;
                if (header.toLowerCase() === 'authorization' && value.startsWith('Bearer ')) {
                    window.__google_auth_token = value.substring(7);
                }
                return originalSetRequestHeader.apply(this, [header, value]);
            };
            
            XMLHttpRequest.prototype.send = function(...args) {
                if (this._headers && this._headers['authorization'] && this._headers['authorization'].startsWith('Bearer ')) {
                    window.__google_auth_token = this._headers['authorization'].substring(7);
                    for (let k in this._headers) {
                        window.__google_headers[k] = this._headers[k];
                    }
                }
                return originalSend.apply(this, args);
            };
        })();
        """
        try:
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': script})
            self.log("   🚀 Đã cài đặt thành công Trình bắt Token Google Labs Flow.")
        except Exception as e:
            self.log(f"   ⚠️ Lỗi cài đặt Trình bắt Token: {e}")

    def _click_create_with_flow_button(self, log_callback) -> bool:
        """Tự động tìm và click nút 'Create with Google Flow' trên giao diện."""
        try:
            from selenium.webdriver.common.by import By
            # Thử click bằng XPath
            try:
                btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Create with Google Flow') or contains(., 'Create with Flow')]")
                btn.click()
                log_callback("✅ Đã click nút 'Create with Google Flow' bằng Selenium.")
                return True
            except Exception:
                pass

            # Thử click bằng JS
            js_code = """
                const selectors = ['button', 'a', 'div', 'span'];
                for (let sel of selectors) {
                    const elements = Array.from(document.querySelectorAll(sel));
                    const el = elements.find(e => {
                        const txt = (e.innerText || e.textContent || "").trim();
                        return txt.includes("Create with Google Flow") || txt.includes("Create with Flow");
                    });
                    if (el) {
                        el.click();
                        return true;
                    }
                }
                return false;
            """
            result = self.driver.execute_script(js_code)
            if result:
                log_callback("✅ Đã click nút 'Create with Google Flow' bằng JavaScript.")
                return True
            return False
        except Exception as e:
            log_callback(f"⚠️ Lỗi khi click nút 'Create with Google Flow': {e}")
            return False

    def auto_extract_credentials_and_create_project(self, log_callback) -> bool:
        """
        Mở Chrome giao diện để tự động trích xuất token qua session API và tự tạo project ID,
        nếu chưa đăng nhập sẽ chuyển sang trang đăng nhập rồi tự quay lại lấy token.
        """
        def _log(msg):
            log_callback(msg)
            self.log(msg)

        try:
            _log("🚀 Khởi chạy trình duyệt Chrome...")
            from app_worker import GOOGLE_PROFILE_PATH
            browser_ok = self.setup_browser(profile_path=GOOGLE_PROFILE_PATH, headless=False)
            if not browser_ok:
                _log("❌ Không khởi động được trình duyệt Chrome.")
                return False
                
            _log("🌐 Điều hướng sang trang Google Labs Flow: https://labs.google/fx/vi/tools/flow...")
            self.driver.get("https://labs.google/fx/vi/tools/flow")
            time.sleep(5)
            
            _log("🔘 Tự động bấm nút 'Create with Google Flow'...")
            self._click_create_with_flow_button(_log)
            time.sleep(4)
            
            _log("🔍 Đang truy cập session API của Google Labs Flow để tự động lấy token...")
            self.driver.get("https://labs.google/fx/api/auth/session")
            time.sleep(3)
            
            # Kiểm tra xem có token sẵn không
            token = None
            try:
                pre_element = self.driver.find_element("xpath", "//pre")
                content = pre_element.text
                data = json.loads(content)
                token = data.get("access_token")
            except Exception:
                pass
                
            if token:
                _log("✅ Đã lấy được Token tự động.")
            else:
                _log("⚠️ Chưa đăng nhập hoặc phiên làm việc hết hạn. Hãy đăng nhập tài khoản Google của bạn...")
                self.driver.get("https://labs.google/fx/vi/tools/flow")
                time.sleep(3)
                self._click_create_with_flow_button(_log)
                
                _log("")
                _log("=" * 60)
                _log("⏳ ĐANG CHỜ BẠN ĐĂNG NHẬP...")
                _log("   Hãy thực hiện đăng nhập tài khoản Google của bạn trên cửa sổ Chrome vừa mở.")
                _log("   Sau khi đăng nhập thành công, hệ thống sẽ tự động bắt token và đóng Chrome.")
                _log("=" * 60)
                _log("")
                
                # Chờ người dùng đăng nhập
                logged_in = False
                start_wait = time.time()
                while time.time() - start_wait < 120:
                    current_url = self.driver.current_url
                    # Kiểm tra xem đã đăng nhập chưa
                    if "signin" not in current_url:
                        # Thử gọi fetch session bằng js
                        token_js = self.driver.execute_script("""
                            return fetch('/fx/api/auth/session')
                                .then(r => r.json())
                                .then(d => d.access_token)
                                .catch(() => null);
                        """)
                        if token_js:
                            token = token_js
                            logged_in = True
                            break
                    time.sleep(2)
                    
                if not logged_in or not token:
                    _log("❌ Quá thời gian chờ (120s) hoặc đăng nhập thất bại.")
                    self.cleanup()
                    return False
                _log("✅ Đăng nhập thành công! Đã trích xuất được Token xác thực.")
                
            # Lấy cookies từ driver
            cookies = {}
            for c in self.driver.get_cookies():
                cookies[c['name']] = c['value']
                
            # Lấy headers user-agent
            user_agent = self.driver.execute_script("return navigator.userAgent;")
            
            # Đóng trình duyệt Chrome
            _log("🔒 Đã thu thập đủ thông tin xác thực. Đang đóng trình duyệt...")
            self.cleanup()
            
            # Gọi API tạo Project mới
            _log("📋 Đang tự động tạo Project mới trên Google Labs Flow qua API...")
            import requests
            from datetime import datetime
            
            token_clean = token.replace("Bearer ", "").replace("bearer ", "").strip()
            bearer_token_formatted = f"Bearer {token_clean}"
            
            project_title = datetime.now().strftime("Replacer Project %b %d - %H:%M")
            create_project_url = "https://labs.google/fx/api/trpc/project.createProject"
            
            api_headers = {
                "Authorization": bearer_token_formatted,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": user_agent,
                "Referer": "https://labs.google/fx/tools/video-fx",
                "Origin": "https://labs.google",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
            
            payload = {
                "json": {
                    "projectTitle": project_title,
                    "toolName": "PINHOLE"
                }
            }
            
            response = requests.post(
                create_project_url,
                json=payload,
                headers=api_headers,
                cookies=cookies,
                timeout=30
            )
            
            project_id = None
            if response.status_code == 200:
                try:
                    data = response.json()
                    project_id = data["result"]["data"]["json"]["result"]["projectId"]
                except Exception:
                    import re
                    match = re.search(r'"projectId":\s*"([^"]+)"', response.text)
                    if match:
                        project_id = match.group(1)
                        
            if not project_id:
                _log("❌ Lỗi API: Không tạo được project mới trên Google Labs. Hãy kiểm tra lại tài khoản hoặc proxy.")
                _log(f"   Chi tiết phản hồi: {response.text[:300]}")
                return False
                
            _log(f"✅ Tạo Project thành công! Project ID: {project_id}")
            
            # Ghi vào file cấu hình labs_credentials.json
            cred_file = os.path.join(BASE_DIR, "labs_credentials.json")
            cred_data = {
                "bearer_token": token_clean,
                "cookies": cookies,
                "headers": {
                    "user-agent": user_agent,
                    "accept": "application/json",
                    "origin": "https://labs.google",
                    "referer": "https://labs.google/"
                },
                "project_id": project_id,
                "updated_at": datetime.now().isoformat()
            }
            
            with open(cred_file, 'w', encoding='utf-8') as f:
                json.dump(cred_data, f, indent=4, ensure_ascii=False)
                
            _log("💾 Đã lưu cấu hình credentials và project ID vào file labs_credentials.json!")
            _log("🎉 BẤT ĐẦU XỬ LÝ: Hệ thống sẵn sàng tạo ảnh ngầm hoàn toàn không cần mở Chrome!")
            return True
            
        except Exception as e:
            _log(f"❌ Lỗi quy trình tự động cấu hình: {e}")
            import traceback
            traceback.print_exc()
            self.cleanup()
            return False

    def generate_image_by_flow(self, prompt: str, aspect_ratio: str = 'IMAGE_ASPECT_RATIO_LANDSCAPE', model: str = 'GEM_PIX_2') -> Optional[str]:
        """
        Tạo ảnh bằng Google Labs Flow chạy ngầm hoàn toàn bằng requests qua API Sandbox,
        né reCAPTCHA bằng cách lấy token từ NestJS server (cổng 3000) giống tool6.py.
        Hỗ trợ tự động thử lại (retry) nếu NestJS hoặc API Google lỗi.
        """
        try:
            import requests
            import random
            
            self.log(f"🎨 [API Ngầm] Bắt đầu tạo ảnh cho prompt: '{prompt[:60]}...'")
            
            # 1. Đọc file cấu hình labs_credentials.json
            cred_file = os.path.join(BASE_DIR, "labs_credentials.json")
            if not os.path.exists(cred_file):
                self.log("❌ Lỗi: Không tìm thấy file labs_credentials.json. Vui lòng bấm 'Lấy Token & Project ID tự động' trước.")
                return None
                
            with open(cred_file, 'r', encoding='utf-8') as f:
                cred = json.load(f)
                
            bearer_token = cred.get("bearer_token")
            cookies = cred.get("cookies", {})
            saved_headers = cred.get("headers", {})
            project_id = cred.get("project_id")
            
            if not bearer_token or not project_id:
                self.log("❌ Lỗi: File cấu hình labs_credentials.json bị thiếu token hoặc project ID. Hãy lấy lại token.")
                return None
                
            max_attempts = 3
            for attempt in range(max_attempts):
                if attempt > 0:
                    self.log(f"   🔄 Thử lại lần thứ {attempt + 1}/{max_attempts} sau 5 giây...")
                    time.sleep(5)
                    
                # 2. Gọi sang API NestJS ở cổng 3000 để lấy recaptcha token + fresh headers
                self.log(f"   🔌 [{attempt + 1}/{max_attempts}] Kết nối tới NestJS Captcha Server (cổng 3000)...")
                try:
                    # Gửi force-refresh
                    try:
                        requests.post("http://localhost:3000/captcha/force-refresh", timeout=3)
                    except Exception:
                        pass
                    time.sleep(1)
                    
                    captcha_res = requests.get(
                        "http://localhost:3000/captcha", 
                        params={"action": "IMAGE_GENERATION"},
                        timeout=65
                    )
                    if captcha_res.status_code != 200:
                        self.log(f"   ⚠️ Lỗi: NestJS Captcha Server trả về HTTP {captcha_res.status_code}.")
                        continue
                        
                    captcha_data = captcha_res.json()
                    recaptcha = captcha_data.get("captcha")
                    fresh_headers = captcha_data.get("headers", {}) or {}
                    
                    if not recaptcha:
                        self.log("   ⚠️ Lỗi: NestJS giải Captcha thất bại (Token rỗng).")
                        continue
                        
                    self.log("   ✅ Đã nhận được Captcha Token thành công!")
                except Exception as e:
                    self.log(f"   ⚠️ Lỗi kết nối tới NestJS Captcha Server: {e}")
                    continue
                    
                # 3. Chuẩn bị headers (merge saved headers với fresh headers từ Chrome)
                headers = {}
                for k, v in saved_headers.items():
                    headers[k.lower()] = v
                for k, v in fresh_headers.items():
                    headers[k.lower()] = v
                    
                headers["authorization"] = f"Bearer {bearer_token}"
                headers["content-type"] = "text/plain;charset=UTF-8"
                headers["origin"] = "https://labs.google"
                headers["referer"] = "https://labs.google/"
                
                # 4. Xác định aspect ratio enum
                ratio_enum = aspect_ratio
                if aspect_ratio == '16:9':
                    ratio_enum = 'IMAGE_ASPECT_RATIO_LANDSCAPE'
                elif aspect_ratio == '9:16':
                    ratio_enum = 'IMAGE_ASPECT_RATIO_PORTRAIT'
                elif aspect_ratio == '1:1':
                    ratio_enum = 'IMAGE_ASPECT_RATIO_SQUARE'
                    
                # 5. Gửi request batchGenerateImages tới Google AI Sandbox
                session_id = f";{int(time.time() * 1000)}"
                dynamic_url = f"https://aisandbox-pa.googleapis.com/v1/projects/{project_id}/flowMedia:batchGenerateImages"
                
                client_context = {
                    "recaptchaContext": {
                        "token": recaptcha,
                        "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB"
                    },
                    "sessionId": session_id,
                    "projectId": project_id, 
                    "tool": "PINHOLE"
                }

                req_item = {
                    "clientContext": client_context,
                    "seed": random.randint(100000, 999999), 
                    "imageModelName": model,           
                    "imageAspectRatio": ratio_enum,
                    "structuredPrompt": {
                        "parts": [{"text": prompt}]
                    },
                    "imageInputs": []
                }

                payload = {
                    "clientContext": client_context,
                    "mediaGenerationContext": {
                        "batchId": str(uuid.uuid4())
                    },
                    "useNewMedia": True,
                    "requests": [req_item]
                }
                
                self.log("   📡 Đang gửi API Request tạo ảnh tới Google AI Sandbox...")
                r = requests.post(dynamic_url, data=json.dumps(payload), headers=headers, cookies=cookies, timeout=60)
                
                if r.status_code == 200:
                    data = r.json()
                    found_imgs = []
                    
                    def recursive_find(node):
                        if isinstance(node, dict):
                            img_data = None
                            img_type = None
                            for k in ["url", "fifeUrl", "imageUrl"]:
                                if k in node and isinstance(node[k], str) and node[k].startswith("http"):
                                    img_data = node[k]
                                    img_type = "url"
                                    break
                            if not img_data:
                                for k in ["base64", "imageBase64", "bytesBase64"]:
                                    if k in node and isinstance(node[k], str) and len(node[k]) > 500:
                                        img_data = node[k]
                                        img_type = "b64"
                                        break
                            if img_data:
                                found_imgs.append({"type": img_type, "data": img_data})
                                return
                            for v in node.values():
                                recursive_find(v)
                        elif isinstance(node, list):
                            for item in node:
                                recursive_find(item)
                                
                    recursive_find(data)
                    
                    if found_imgs:
                        item = found_imgs[0]
                        if item["type"] == "b64":
                            self.log("   ✅ Sinh ảnh qua API thành công!")
                            return item["data"]
                        elif item["type"] == "url":
                            img_url = item["data"]
                            if "googleusercontent" in img_url and "=s" not in img_url:
                                img_url += "=s0"
                            res_img = requests.get(img_url, timeout=30)
                            if res_img.status_code == 200:
                                self.log("   ✅ Tải ảnh từ URL Google Storage thành công!")
                                return base64.b64encode(res_img.content).decode('utf-8')
                                
                    # Xử lý các lỗi Safety Filter
                    if "SAFETY" in r.text or "filter" in r.text.lower():
                        self.log("   ❌ Bị Safety Filter của Google chặn prompt này.")
                        return None # Nếu bị safety thì dừng ngay, không cần retry
                    else:
                        self.log(f"   ⚠️ API không trả về ảnh. Response snippet: {r.text[:300]}")
                else:
                    self.log(f"   ⚠️ Lỗi API Google Sandbox (HTTP {r.status_code}): {r.text[:300]}")
                    if r.status_code == 403:
                        self.log("   👉 Có thể token bị hết hạn. Hãy bấm 'Lấy Token & Project ID tự động' lại để làm mới token.")
                        
            self.log("❌ Sinh ảnh thất bại sau nhiều lần thử lại.")
        except Exception as e:
            self.log(f"❌ Lỗi trong quá trình sinh ảnh ngầm: {e}")
        return None

    def cleanup(self):
        """Đóng trình duyệt và giải phóng driver."""
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None
        self._script_injected = False
