import subprocess
import sys
from pathlib import Path


def main():
    repo_root = Path(__file__).resolve().parent
    wopc_script = repo_root / "launcher" / "wopc.py"

    if not wopc_script.exists():
        print(f"Error: {wopc_script} not found.")
        sys.exit(1)

    print("Building WOPC Launcher executable with PyInstaller...")

    # We use subprocess to call pyinstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--icon=launcher/gui/wopc.ico",
        "--name",
        "WOPC-Launcher",
        # Ensure we collect CustomTkinter assets
        "--collect-all",
        "customtkinter",
        "--add-data",
        f"{repo_root / 'init'};init",
        "--add-data",
        f"{repo_root / 'gamedata'};gamedata",
        "--add-data",
        f"{repo_root / 'vendor'};vendor",
        "--add-data",
        f"{repo_root / 'launcher' / 'gui' / 'wopc.ico'};launcher/gui",
        str(wopc_script),
    ]

    result = subprocess.run(cmd, cwd=str(repo_root))
    if result.returncode == 0:
        print("\nBuild successful! Executable is located in the 'dist/WOPC-Launcher' folder.")
    else:
        print("\nBuild failed.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
