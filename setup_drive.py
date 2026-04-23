"""
One-time Google Drive OAuth setup script.
Run this once to authorize, then the app will use the saved token.
"""
import os
import json

# Check dependencies
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    print("Installing required packages...")
    os.system("pip install google-auth-oauthlib google-api-python-client")
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def main():
    print("=" * 50)
    print("  Google Drive OAuth Setup")
    print("=" * 50)

    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"\n❌ File tidak ditemukan: {CLIENT_SECRET_FILE}")
        print("\nCaranya:")
        print("1. Buka https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth Client ID → type: Desktop App")
        print("3. Download JSON → rename ke client_secret.json")
        print(f"4. Simpan di: {BASE_DIR}")
        return

    print("\n🔐 Membuka browser untuk login Google...")
    print("   Pilih akun Google Anda dan klik 'Allow'\n")

    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE, SCOPES
    )
    creds = flow.run_local_server(port=8090)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    # Test connection
    service = build("drive", "v3", credentials=creds)
    results = service.files().list(pageSize=3, fields="files(id, name)").execute()
    files = results.get("files", [])

    print("\n✅ Login berhasil!")
    print(f"   Token tersimpan di: {TOKEN_FILE}")
    print(f"   Files found: {len(files)}")
    for f in files:
        print(f"   - {f['name']}")

    print("\n🚀 Sekarang jalankan: python app.py")
    print("   App akan otomatis menggunakan token ini.")

if __name__ == "__main__":
    main()
