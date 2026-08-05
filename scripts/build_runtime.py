"""Build the standalone GraphCoder runtime for Electron packaging."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "build" / "runtime-dist"
WORK = ROOT / "build" / "runtime-work"
TARGET = ROOT / "desktop" / "runtime"


def main() -> None:
    """Run PyInstaller and place the native executable in desktop/runtime."""
    executable = "graphcoder-runtime.exe" if platform.system() == "Windows" else "graphcoder-runtime"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK),
        str(ROOT / "packaging" / "graphcoder-runtime.spec"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)

    source = DIST / executable
    if not source.is_file():
        raise FileNotFoundError(f"PyInstaller did not create {source}")
    shutil.rmtree(TARGET, ignore_errors=True)
    TARGET.mkdir(parents=True)
    destination = TARGET / executable
    shutil.copy2(source, destination)
    destination.chmod(destination.stat().st_mode | 0o111)
    size_mb = destination.stat().st_size / 1024 / 1024
    print(f"Runtime ready: {destination} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
