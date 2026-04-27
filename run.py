"""Einstiegspunkt für den Marktcrawler."""
from pathlib import Path
from dotenv import load_dotenv

# .env laden falls vorhanden (lokale Entwicklung)
load_dotenv(Path(__file__).parent / ".env")

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
