# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPECPATH).parent
hiddenimports = []


def runtime_module(name):
    excluded = (".tests", ".test_", "._test_", ".benchmarks", ".helpers")
    return not any(part in name for part in excluded)


for package in (
    "aiosqlite",
    "anthropic",
    "google.genai",
    "httpx",
    "jsonschema",
    "ollama",
    "openai",
):
    hiddenimports.extend(collect_submodules(package, filter=runtime_module))
hiddenimports.extend(
    collect_submodules(
        "mcp",
        filter=lambda name: runtime_module(name) and not name.startswith("mcp.cli"),
    )
)

datas = collect_data_files("certifi") + collect_data_files("jsonschema")

a = Analysis(
    [str(ROOT / "packaging" / "runtime_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "fastapi",
        "langchain",
        "langchain_openai",
        "langgraph",
        "rich",
        "textual",
        "uvicorn",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="graphcoder-runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
