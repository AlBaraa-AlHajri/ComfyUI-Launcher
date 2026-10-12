# PyInstaller resources stay beside the executable in an onedir bundle.
# تبقى الموارد مع الملف التنفيذي داخل مجلد الحزمة.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
data = collect_data_files("customtkinter")
data += [(str(root / "assets"), "assets"),
         (str(root / "src/comfy_launcher/worker.py"), "."),
         (str(root / "LICENSE"), ".")]
a = Analysis([str(root / "src/comfy_launcher/__main__.py")],
             pathex=[str(root / "src")], binaries=[], datas=data,
             hiddenimports=["pystray._win32"], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ComfyUI-Launcher",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / "assets/icon.ico"), version=str(root / "version_info.txt"),
          uac_admin=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ComfyUI-Launcher")
