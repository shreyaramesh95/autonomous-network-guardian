"""Entrypoint: `python app.py` or `flask --app app run`."""
from __future__ import annotations

from ang import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
