"""Windows-Einstiegspunkt: startet Flask-Server, öffnet Browser, zeigt Tray-Icon."""

import os
import sys
import socket
import threading
import time
import webbrowser

# DATA_DIR vor allen App-Imports setzen, da app/__init__.py es beim Import liest
if getattr(sys, "frozen", False):
    _data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Marktcrawler")
else:
    _data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(_data_dir, exist_ok=True)
os.environ["DATA_DIR"] = _data_dir

PORT = 5000
URL = f"http://localhost:{PORT}"


def _server_ready(timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.4)
    return False


def _run_flask():
    from app import create_app
    flask_app = create_app()
    flask_app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


def _build_tray_icon():
    from PIL import Image, ImageDraw, ImageFont
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, size - 3, size - 3], fill="#2563eb")
    try:
        font = ImageFont.truetype("arialbd.ttf", 30)
    except OSError:
        font = ImageFont.load_default(size=30)
    bbox = d.textbbox((0, 0), "M", font=font)
    x = (size - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (size - (bbox[3] - bbox[1])) // 2 - bbox[1]
    d.text((x, y), "M", fill="white", font=font)
    return img


def main():
    # Flask-Server im Hintergrund starten
    threading.Thread(target=_run_flask, daemon=True).start()

    # Browser öffnen sobald Server bereit
    def _open():
        if _server_ready():
            webbrowser.open(URL)
    threading.Thread(target=_open, daemon=True).start()

    # Tray-Icon (benötigt pystray + Pillow)
    try:
        import pystray

        def _on_open(icon, item):
            webbrowser.open(URL)

        def _on_quit(icon, item):
            icon.stop()
            os._exit(0)

        icon = pystray.Icon(
            "Marktcrawler",
            _build_tray_icon(),
            "Marktcrawler",
            menu=pystray.Menu(
                pystray.MenuItem("Dashboard öffnen", _on_open, default=True),
                pystray.MenuItem("Beenden", _on_quit),
            ),
        )
        icon.run()
    except Exception:
        # Fallback ohne Tray: blockiert bis Server-Thread endet
        while True:
            time.sleep(60)


if __name__ == "__main__":
    main()
