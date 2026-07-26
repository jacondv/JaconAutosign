# PyInstaller spec - build che do --onedir de khoi dong nhanh (< 10s, yeu cau cua nguoi dung).
# Chay: pyinstaller autosign.spec
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

ICON_PATH = "src/autosign/ui/asset/AutoSign.ico"

datas = []
datas += collect_data_files("pypdfium2")
datas += [(ICON_PATH, "autosign/ui/asset")]

a = Analysis(
    ["entry_point.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoSign",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON_PATH,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AutoSign",
)
