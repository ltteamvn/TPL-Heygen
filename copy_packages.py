import os
import sys
import shutil
import site

def copy_packages(dest_dir):
    # Lay tat ca cac site-packages hop le tu sys.path, site.getsitepackages() va site.getusersitepackages()
    site_packages_paths = []
    
    # 1. Uu tien sys.path (hoat dong chinh xac khi dung Virtualenv/Venv)
    for p in sys.path:
        if p and p.endswith("site-packages") and os.path.exists(p):
            if p not in site_packages_paths:
                site_packages_paths.append(p)
                
    # 2. Lay tu site.getusersitepackages() (dung khi cai bang pip install --user)
    try:
        user_site = site.getusersitepackages()
        if user_site and os.path.exists(user_site):
            if user_site not in site_packages_paths:
                site_packages_paths.append(user_site)
    except Exception:
        pass

    # 3. Fallback sang site.getsitepackages() cua Python he thong
    try:
        for d in site.getsitepackages():
            if "site-packages" in d and os.path.exists(d):
                if d not in site_packages_paths:
                    site_packages_paths.append(d)
    except Exception:
        pass

    if not site_packages_paths:
        print("[Error] Khong tim thay bat ky thu muc site-packages nao!")
        return

    print("Site-packages directories found:")
    for path in site_packages_paths:
        print(f" - {path}")
    print(f"Destination path: {dest_dir}")
    
    packages_to_copy = [
        # === UI / Browser ===
        "PySide6", "shiboken6", "qfluentwidgets", "selenium", 
        "requests", "urllib3", "certifi", "idna", "charset_normalizer",
        "websocket", "websockets", "pyperclip", "undetected_chromedriver", "darkdetect", "qframelesswindow",
        
        # === Whisper + PyTorch (CPU) ===
        "whisper", "torch", "torchgen",

        # === NumPy stack ===
        "numpy", "numpy.libs",

        # === Numba + LLVM (bắt buộc cho whisper.timing) ===
        "numba", "llvmlite",

        # === Audio processing ===
        "librosa", "soundfile", "audioread", "resampy",
        "soxr", "pooch", "lazy_loader", "msgpack",
        "joblib", "scikit-learn", "sklearn", "decorator",
        "scipy",

        # === Whisper tokenizer ===
        "tiktoken", "tiktoken_ext", "regex",


        # === PyTorch utilities ===
        "tqdm", "filelock", "sympy", "networkx", "jinja2", "mpmath",
        "fsspec", "safetensors", "more_itertools", "huggingface_hub",

        # === Misc ===
        "packaging", "platformdirs", "requests_toolbelt",
    ]

    # --- Danh sach cac file .py don le ---
    files_to_copy = ["typing_extensions.py"]

    for pkg in packages_to_copy:
        copied = False
        for site_path in site_packages_paths:
            src = os.path.join(site_path, pkg)
            dst = os.path.join(dest_dir, pkg)
            if os.path.exists(src):
                print(f"Copying package: {pkg} from {site_path}...")
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                copied = True
                break
        if not copied:
            # Tìm file .py đơn lẻ
            for site_path in site_packages_paths:
                src_py = os.path.join(site_path, f"{pkg}.py")
                dst_py = os.path.join(dest_dir, f"{pkg}.py")
                if os.path.exists(src_py):
                    print(f"Copying file: {pkg}.py from {site_path}...")
                    shutil.copy2(src_py, dst_py)
                    copied = True
                    break
        if not copied:
            print(f"[Skip] Package not found (optional): {pkg}")

    # --- Copy file .py don le ---
    for f_name in files_to_copy:
        for site_path in site_packages_paths:
            src_f = os.path.join(site_path, f_name)
            if os.path.exists(src_f):
                shutil.copy2(src_f, os.path.join(dest_dir, f_name))
                print(f"Copying file: {f_name} from {site_path}...")
                break

    # Copy cac file cua du an
    local_files = ["app_config.json", "labs_credentials.json", "logo.ico"]
    for f in local_files:
        src_f = os.path.join(os.path.dirname(__file__), f)
        dst_f = os.path.join(dest_dir, f)
        if os.path.exists(src_f):
            shutil.copy2(src_f, dst_f)
            print(f"Copied local file: {f}")

    # Copy cac thu muc con cua du an: extension, ffmpeg, chrome_bin
    local_dirs = ["extension", "ffmpeg", "chrome_bin", "whisper_models"]
    for d in local_dirs:
        src_d = os.path.join(os.path.dirname(__file__), d)
        dst_d = os.path.join(dest_dir, d)
        if os.path.exists(src_d):
            if os.path.exists(dst_d):
                shutil.rmtree(dst_d)
            shutil.copytree(src_d, dst_d)
            print(f"Copied local dir: {d}")

    # Copy CaptchaServer.exe vao thu muc dich
    captcha_exe = os.path.join(os.path.dirname(__file__), "CaptchaServer.exe")
    if os.path.exists(captcha_exe):
        shutil.copy2(captcha_exe, os.path.join(dest_dir, "CaptchaServer.exe"))
        print("Copied CaptchaServer.exe")

    # Copy TAT CA file DLL tu thu muc Python de tranh loi LoadLibraryExW cho .pyd
    python_dir = os.path.dirname(sys.executable)
    print(f"\nCopying all runtime DLLs from Python dir: {python_dir}")
    dll_count = 0
    for fname in os.listdir(python_dir):
        if fname.lower().endswith(".dll"):
            src_dll = os.path.join(python_dir, fname)
            dst_dll = os.path.join(dest_dir, fname)
            if not os.path.exists(dst_dll):
                shutil.copy2(src_dll, dst_dll)
                print(f"  Copied DLL: {fname}")
                dll_count += 1
    print(f"Total DLLs copied: {dll_count}")

    # Also copy llvmlite's binding DLL (libllvm) nếu có
    for site_path in site_packages_paths:
        llvm_binding_dir = os.path.join(site_path, "llvmlite", "binding")
        if os.path.exists(llvm_binding_dir):
            for fname in os.listdir(llvm_binding_dir):
                if fname.lower().endswith(".dll"):
                    src_dll = os.path.join(llvm_binding_dir, fname)
                    dst_dll = os.path.join(dest_dir, "llvmlite", "binding", fname)
                    if not os.path.exists(dst_dll):
                        shutil.copy2(src_dll, dst_dll)
                        print(f"  Copied llvmlite binding DLL: {fname}")


    # Tao file qt.conf de cau hinh duong dan plugins cho PySide6
    qt_conf_path = os.path.join(dest_dir, "qt.conf")
    try:
        with open(qt_conf_path, "w", encoding="utf-8") as f:
            f.write("[Paths]\nPrefix = PySide6\nPlugins = plugins\n")
        print("Created qt.conf successfully")
    except Exception as e:
        print(f"[Warning] Khong the tao file qt.conf: {e}")

    # Chuan hoa ten cac file .pyd de Nuitka nap duoc o runtime
    normalize_pyd_extensions(dest_dir)

    # Patch whisper/timing.py de numba la tuy chon (tranh loi llvmlite.dll)
    patch_whisper_timing(dest_dir)

    # Patch undetected_chromedriver/patcher.py de loai bo distutils (tranh loi Python 3.13)
    patch_undetected_chromedriver(dest_dir)

    # Thu thap va copy cac file pywin32 vao goc cua thu muc phan phoi
    copy_pywin32(dest_dir)


    # Clean __pycache__ and bytecode files to force recompilation of patched modules
    clean_pycache(dest_dir)


def clean_pycache(dest_dir):
    print("Cleaning __pycache__ and compiled python files (.pyc, .pyo)...")
    deleted_dirs = 0
    deleted_files = 0
    for root, dirs, files in os.walk(dest_dir, topdown=False):
        for file in files:
            if file.endswith((".pyc", ".pyo")):
                try:
                    os.remove(os.path.join(root, file))
                    deleted_files += 1
                except Exception as e:
                    print(f"[Warning] Khong the xoa file bytecode {file}: {e}")
        
        for d in dirs:
            if d == "__pycache__":
                dir_path = os.path.join(root, d)
                try:
                    shutil.rmtree(dir_path)
                    deleted_dirs += 1
                except Exception as e:
                    print(f"[Warning] Khong the xoa thu muc pycache {dir_path}: {e}")
                    
    print(f"Cleaned up {deleted_dirs} __pycache__ directories and {deleted_files} bytecode files.")


def patch_whisper_timing(dest_dir):
    """Xoa hoan toan numba ra khoi whisper/timing.py trong thu muc dist.

    Luon lay file goc tu site-packages truoc de dam bao patch sach.
    numba chi dung @jit de toi uu backtrace() va dtw_cpu() (toc do),
    khong anh huong den ket qua phu de. Cac ham van chay dung
    bang pure Python/numpy, khong can numba/llvmlite.dll.
    """
    import re
    timing_path = os.path.join(dest_dir, "whisper", "timing.py")
    if not os.path.exists(timing_path):
        print("[Skip] whisper/timing.py not found in dist, skipping patch")
        return

    # Luon lay file goc tu site-packages de tranh patch chong cheo
    original_timing = None
    for sp in site_packages_paths if 'site_packages_paths' in dir() else site.getsitepackages():
        candidate = os.path.join(sp, "whisper", "timing.py")
        if os.path.exists(candidate):
            original_timing = candidate
            break

    if original_timing:
        shutil.copy2(original_timing, timing_path)

    with open(timing_path, encoding="utf-8") as f:
        content = f.read()

    original = content

    # 1. Xoa dong "import numba"
    content = re.sub(r'^import numba\s*\n', '# [PATCHED: numba removed]\n', content, flags=re.MULTILINE)

    # 2. Xoa tat ca decorator @numba.jit(...)
    content = re.sub(r'@numba\.jit\([^)]*\)\s*\n', '', content)

    if content == original:
        print("[Warning] Could not patch timing.py (pattern not found)")
        return

    with open(timing_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Xoa file .bak neu co (tranh lam to bộ cai)
    bak_path = timing_path + ".bak"
    if os.path.exists(bak_path):
        os.remove(bak_path)

    print("Patched whisper/timing.py: REMOVED numba entirely (no llvmlite.dll needed)")
def patch_undetected_chromedriver(dest_dir):
    """Patch undetected_chromedriver/patcher.py de loai bo distutils.
    
    Python 3.12+ deprecated va Python 3.13 da xoa hoan toan distutils.
    Ta thay the LooseVersion bang class gia lap dung packaging.version.Version de tranh loi runtime.
    """
    import re
    patcher_path = os.path.join(dest_dir, "undetected_chromedriver", "patcher.py")
    if not os.path.exists(patcher_path):
        print("[Skip] undetected_chromedriver/patcher.py not found in dist, skipping patch")
        return

    with open(patcher_path, encoding="utf-8") as f:
        content = f.read()

    # Kiem tra neu da duoc patch voi method _parse roi
    if "def _parse" in content:
        print("[Skip] undetected_chromedriver/patcher.py already patched with version parsing")
        return

    old_import = "from distutils.version import LooseVersion"
    
    # Class gia lap LooseVersion dung packaging va ho tro thuoc tinh version
    new_implementation = """class LooseVersion:
    def __init__(self, version_str):
        self.vstring = str(version_str)
        self.version = self._parse(self.vstring)
    def _parse(self, version_str):
        import re
        components = [x for x in re.split(r'(\d+)', version_str) if x]
        version_list = []
        for c in components:
            if c.isdigit():
                version_list.append(int(c))
            elif c != '.' and c != '-' and c != '_':
                version_list.append(c)
        return version_list
    def __str__(self):
        return self.vstring
    def __repr__(self):
        return f"LooseVersion('{self.vstring}')"
    def _key(self):
        from packaging.version import Version
        try:
            return Version(self.vstring)
        except Exception:
            return self.vstring
    def __eq__(self, other):
        if not isinstance(other, LooseVersion):
            return NotImplemented
        return self._key() == other._key()
    def __lt__(self, other):
        if not isinstance(other, LooseVersion):
            return NotImplemented
        return self._key() < other._key()
    def __le__(self, other):
        if not isinstance(other, LooseVersion):
            return NotImplemented
        return self._key() <= other._key()
    def __gt__(self, other):
        if not isinstance(other, LooseVersion):
            return NotImplemented
        return self._key() > other._key()
    def __ge__(self, other):
        if not isinstance(other, LooseVersion):
            return NotImplemented
        return self._key() >= other._key()"""

    patched = content
    if old_import in content:
        patched = content.replace(old_import, new_implementation, 1)
    elif "class LooseVersion" in content:
        patched = re.sub(
            r'class LooseVersion:.*?return self\._key\(\) >= other\._key\(\)',
            new_implementation,
            content,
            flags=re.DOTALL
        )

    if patched == content:
        print("[Warning] Could not patch undetected_chromedriver/patcher.py (pattern not found)")
        return

    with open(patcher_path, "w", encoding="utf-8") as f:
        f.write(patched)
    print("Patched undetected_chromedriver/patcher.py: replaced distutils.LooseVersion with custom packaging.LooseVersion")
def copy_pywin32(dest_dir):
    """Copy pywin32 modules to the root of dest_dir so they are importable.
    
    pywin32 usually relies on pywin32.pth to add win32 and win32/lib to sys.path.
    In standalone dist, we copy the .pyd files from win32 and .py files from win32/lib
    directly to the root of dest_dir to make them importable as win32gui, win32con, etc.
    """
    import site
    print("Collecting pywin32 files...")
    # Tim thu muc win32 trong site-packages
    win32_src = None
    for sp in site_packages_paths if 'site_packages_paths' in dir() else site.getsitepackages():
        candidate = os.path.join(sp, "win32")
        if os.path.exists(candidate):
            win32_src = candidate
            break
            
    if not win32_src:
        # Thu them vi tri Roaming user site-packages neu co
        try:
            user_site = site.getusersitepackages()
            candidate = os.path.join(user_site, "win32")
            if os.path.exists(candidate):
                win32_src = candidate
        except Exception:
            pass
            
    if not win32_src:
        print("[Warning] pywin32 (win32) folder not found, skipping pywin32 copy")
        return
        
    print(f"Found pywin32 at: {win32_src}")
        
    # 1. Copy cac file .pyd truc tiep vao goc cua dest_dir
    copied_count = 0
    for file in os.listdir(win32_src):
        if file.endswith((".pyd", ".py")):
            src_file = os.path.join(win32_src, file)
            dst_file = os.path.join(dest_dir, file)
            if not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
                copied_count += 1
                
    # 2. Copy cac file .py tu win32/lib (vi du: win32con.py)
    win32_lib = os.path.join(win32_src, "lib")
    if os.path.exists(win32_lib):
        for file in os.listdir(win32_lib):
            if file.endswith(".py"):
                src_file = os.path.join(win32_lib, file)
                dst_file = os.path.join(dest_dir, file)
                if not os.path.exists(dst_file):
                    shutil.copy2(src_file, dst_file)
                    copied_count += 1
                    
    print(f"Copied {copied_count} pywin32 files to dist root.")


def normalize_pyd_extensions(dest_dir):
    print("Normalizing C-extension (.pyd) filenames...")
    for root, dirs, files in os.walk(dest_dir):
        for file in files:
            if file.endswith(".pyd") and ".cp" in file:
                # Vi du: _tiktoken.cp313-win_amd64.pyd -> _tiktoken.pyd
                parts = file.split(".")
                name = parts[0]
                new_name = f"{name}.pyd"
                
                src_path = os.path.join(root, file)
                dst_path = os.path.join(root, new_name)
                
                if not os.path.exists(dst_path):
                    try:
                        shutil.copy2(src_path, dst_path)
                        print(f"Normalized: {file} -> {new_name}")
                    except Exception as e:
                        print(f"[Warning] Khong the copy/rename file {file}: {e}")

def copy_project_assets(dest_dir):
    """Copy thư mục ffmpeg, extension, whisper_models, logo.ico và các file phụ trợ vào thư mục build."""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Copy thư mục ffmpeg
    src_ffmpeg = os.path.join(BASE_DIR, "ffmpeg")
    dst_ffmpeg = os.path.join(dest_dir, "ffmpeg")
    if os.path.exists(src_ffmpeg):
        print("Copying ffmpeg directory...")
        if os.path.exists(dst_ffmpeg):
            shutil.rmtree(dst_ffmpeg)
        shutil.copytree(src_ffmpeg, dst_ffmpeg)
        
        # Copy trực tiếp ffmpeg.exe & ffprobe.exe lên thư mục gốc dest_dir để đảm bảo 100% không bao giờ sót
        for exe_name in ["ffmpeg.exe", "ffprobe.exe"]:
            exe_src = os.path.join(src_ffmpeg, exe_name)
            exe_dst = os.path.join(dest_dir, exe_name)
            if os.path.exists(exe_src):
                shutil.copy2(exe_src, exe_dst)

    # 2. Copy thư mục extension
    src_ext = os.path.join(BASE_DIR, "extension")
    dst_ext = os.path.join(dest_dir, "extension")
    if os.path.exists(src_ext):
        print("Copying extension directory...")
        if os.path.exists(dst_ext):
            shutil.rmtree(dst_ext)
        shutil.copytree(src_ext, dst_ext)

    # 3. Copy thư mục whisper_models (nếu có)
    src_wm = os.path.join(BASE_DIR, "whisper_models")
    dst_wm = os.path.join(dest_dir, "whisper_models")
    if os.path.exists(src_wm):
        print("Copying whisper_models directory...")
        if os.path.exists(dst_wm):
            shutil.rmtree(dst_wm)
        shutil.copytree(src_wm, dst_wm)

    # 4. Copy các file riêng lẻ: logo.ico, CaptchaServer.exe, app_config.json
    asset_files = ["logo.ico", "CaptchaServer.exe", "app_config.json"]
    for file_name in asset_files:
        src_f = os.path.join(BASE_DIR, file_name)
        dst_f = os.path.join(dest_dir, file_name)
        if os.path.exists(src_f):
            print(f"Copying file {file_name}...")
            shutil.copy2(src_f, dst_f)

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(BASE_DIR, "build_out")
    
    src_dist = os.path.join(build_dir, "main.dist")
    dest_dist = os.path.join(build_dir, "TPL_Heygen.dist")
    
    # 1. Doi ten thu muc main.dist thanh TPL_Heygen.dist bang Python de tranh loi lenh CMD
    if os.path.exists(src_dist):
        print("Renaming main.dist to TPL_Heygen.dist...")
        if os.path.exists(dest_dist):
            try:
                shutil.rmtree(dest_dist)
            except Exception:
                pass
        try:
            os.rename(src_dist, dest_dist)
        except Exception as e:
            print(f"[Warning] Khong the doi ten thu muc main.dist: {e}")
            
    # 2. Doi ten file main.exe thanh TPL_Heygen.exe
    src_exe = os.path.join(dest_dist, "main.exe")
    dest_exe = os.path.join(dest_dist, "TPL_Heygen.exe")
    if os.path.exists(src_exe):
        print("Renaming main.exe to TPL_Heygen.exe...")
        if os.path.exists(dest_exe):
            try:
                os.remove(dest_exe)
            except Exception:
                pass
        try:
            os.rename(src_exe, dest_exe)
        except Exception as e:
            print(f"[Warning] Khong the doi ten file main.exe: {e}")

    # 3. Tien hanh copy cac thu vien va assets cua du an
    if os.path.exists(dest_dist):
        copy_packages(dest_dist)
        copy_project_assets(dest_dist)
        print("Success: Copied all packages and files!")
    else:
        print("[Error] Khong tim thay thu muc phan phoi TPL_Heygen.dist. Hay chac chan Nuitka da build thanh cong!")

