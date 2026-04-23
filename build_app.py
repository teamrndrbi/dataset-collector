"""
Build script for Dataset Collector desktop app.
Run: python build_app.py
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    print("=" * 50)
    print("  Building Dataset Collector Desktop App")
    print("=" * 50)

    # Check PyInstaller
    try:
        import PyInstaller
        print(f"  PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("  Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Determine platform
    if sys.platform == "darwin":
        platform_name = "macOS"
        icon_option = []  # No icon for now
    elif sys.platform == "win32":
        platform_name = "Windows"
        icon_option = []
    else:
        platform_name = "Linux"
        icon_option = []

    print(f"  Platform: {platform_name}")
    print(f"  Building...")

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "DatasetCollector",
        "--noconfirm",
        "--clean",
        # Add data files
        "--add-data", f"templates{os.pathsep}templates",
        "--add-data", f"static{os.pathsep}static",
        "--add-data", f"client_secret.json{os.pathsep}.",
        # Hidden imports needed by google libraries
        "--hidden-import", "google.auth.transport.requests",
        "--hidden-import", "google_auth_oauthlib",
        "--hidden-import", "google_auth_oauthlib.flow",
        "--hidden-import", "googleapiclient.discovery",
        "--hidden-import", "googleapiclient._helpers",
        "--hidden-import", "google.oauth2.credentials",
        # Collect all google packages
        "--collect-all", "google.auth",
        "--collect-all", "google_auth_oauthlib",
        "--collect-all", "googleapiclient",
        # Entry point
        "launcher.py",
    ] + icon_option

    print(f"\n  Running: {' '.join(cmd[:6])}...")
    subprocess.check_call(cmd, cwd=BASE_DIR)

    dist_dir = os.path.join(BASE_DIR, "dist", "DatasetCollector")

    print("\n" + "=" * 50)
    print("  ✅ BUILD SUCCESSFUL!")
    print("=" * 50)
    print(f"  Output: {dist_dir}")
    print(f"\n  To run: ./dist/DatasetCollector/DatasetCollector")
    print(f"\n  To distribute:")
    print(f"  1. Zip the folder: dist/DatasetCollector/")
    print(f"  2. Share the zip file")
    print(f"  3. User extracts and double-clicks DatasetCollector")
    print("=" * 50)


if __name__ == "__main__":
    main()
