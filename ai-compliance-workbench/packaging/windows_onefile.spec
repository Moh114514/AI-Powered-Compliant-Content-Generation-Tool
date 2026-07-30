# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
datas = [
    (str(ROOT / "data" / "compliance"), "data/compliance"),
    (str(ROOT / "data" / "brand_profiles"), "data/brand_profiles"),
    (str(ROOT / "data" / "prompts"), "data/prompts"),
    (str(ROOT / "data" / "demo"), "data/demo"),
    (str(ROOT / "frontend" / "dist"), "frontend_dist"),
    (str(ROOT / ".env"), "."),
    (str(ROOT / ".env.example"), "."),
]

prompt_collection = ROOT.parent / "医美内容生成_全场景提示词合集_v1.0.md"
if prompt_collection.exists():
    datas.append((str(prompt_collection), "data/prompts"))

hiddenimports = collect_submodules("uvicorn")

a = Analysis(
    [str(ROOT / "packaging" / "desktop_launcher.py")],
    pathex=[str(ROOT / "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter.test"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AI_Compliance_Workbench",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
