#!/usr/bin/env python3
"""
Build script for SnakeV2 standalone executable.

Usage:
    python build.py

Requires PyInstaller:
    pip install pyinstaller

This builds a single-file executable named "SnakeV2" (or "SnakeV2.exe"
on Windows) in the `dist/` directory.

Flags:
    --onefile    (default) Single executable
    --onedir     Directory with supporting files
    --windowed   No console window (Windows/macOS GUI app)
    --console    Show console window (useful for debugging)

Cross-platform notes:
    macOS:  pyinstaller --name SnakeV2 --onefile --windowed main.py
    Linux:  pyinstaller --name SnakeV2 --onefile --windowed main.py
    Windows: pyinstaller --name SnakeV2 --onefile --windowed main.py
"""

import subprocess
import sys

def main():
    args = [
        "pyinstaller",
        "--name", "SnakeV2",
        "--onefile",
        "--windowed",
        "--add-data", "README.md:.",
        "--add-data", "__version__.__py__:.",
    ]

    if "--onedir" in sys.argv:
        args[args.index("--onefile")] = "--onedir"

    if "--console" in sys.argv:
        args[args.index("--windowed")] = "--console"

    args.append("main.py")

    print("Running:", " ".join(args))
    subprocess.check_call(args)
    print("\nBuild complete! Executable is in dist/SnakeV2")


if __name__ == "__main__":
    main()
