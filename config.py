import os
import secrets
import logging as _logging
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = os.getenv("GUILD_ID", "")
_default_db = "/tmp/listings.db" if os.environ.get("VERCEL") == "1" else "listings.db"
DB_PATH = os.getenv("DB_PATH", _default_db)
DISCORD_ERROR_WEBHOOK = os.getenv("DISCORD_ERROR_WEBHOOK", "")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
if not FLASK_SECRET_KEY:
    FLASK_SECRET_KEY = secrets.token_hex(32)
    _logging.warning(
        "FLASK_SECRET_KEY not set in .env — using a random key. "
        "All sessions will be invalidated on restart. "
        "Set FLASK_SECRET_KEY in .env to persist sessions."
    )
