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
        "PySide6", "shiboken6", "qfluentwidgets", "selenium", 
        "requests", "urllib3", "certifi", "idna", "charset_normalizer",
        "websocket"
    ]

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
            else:
                # Thu tim file don .py
                src_py = os.path.join(site_path, f"{pkg}.py")
                dst_py = os.path.join(dest_dir, f"{pkg}.py")
                if os.path.exists(src_py):
                    print(f"Copying file: {pkg}.py from {site_path}...")
                    shutil.copy2(src_py, dst_py)
                    copied = True
                    break
        if not copied:
            print(f"[Warning] Khong tim thay package: {pkg}")

    # Copy cac file cua du an
    local_files = ["app_config.json", "labs_credentials.json", "logo.ico"]
    for f in local_files:
        src_f = os.path.join(os.path.dirname(__file__), f)
        dst_f = os.path.join(dest_dir, f)
        if os.path.exists(src_f):
            shutil.copy2(src_f, dst_f)
            print(f"Copied local file: {f}")

    # Copy cac thu muc con cua du an: extension, ffmpeg, chrome_bin
    local_dirs = ["extension", "ffmpeg", "chrome_bin"]
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

    # 3. Tien hanh copy cac thu vien
    if os.path.exists(dest_dist):
        copy_packages(dest_dist)
        print("Success: Copied all packages and files!")
    else:
        print("[Error] Khong tim thay thu muc phan phoi TPL_Heygen.dist. Hay chac chan Nuitka da build thanh cong!")
