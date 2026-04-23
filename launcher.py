"""
Dataset Collector — Desktop Launcher
Starts Flask server and opens browser automatically.
"""

import os
import sys
import time
import socket
import signal
import threading
import webbrowser


def find_free_port():
    """Find an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def wait_for_server(port, timeout=10):
    """Wait until the server is ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.2)
    return False


def main():
    port = 5001

    # Try to find free port if 5001 is in use
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
    except OSError:
        port = find_free_port()

    print("=" * 50)
    print("  📸 Dataset Collector")
    print("=" * 50)
    print(f"  Starting on port {port}...")

    # Import and configure Flask app
    from app import app as flask_app

    # Open browser after server starts
    def open_browser():
        if wait_for_server(port):
            url = f"http://localhost:{port}"
            print(f"  🌐 Opening {url}")
            webbrowser.open(url)
        else:
            print("  ⚠️  Server failed to start!")

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n  👋 Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Start Flask (no debug in production/frozen mode)
    is_frozen = getattr(sys, 'frozen', False)
    print(f"  Mode: {'Desktop App' if is_frozen else 'Development'}")
    print("  Press Ctrl+C to stop")
    print("=" * 50)

    flask_app.run(
        host='127.0.0.1',
        port=port,
        debug=not is_frozen,
        use_reloader=not is_frozen
    )


if __name__ == '__main__':
    main()
