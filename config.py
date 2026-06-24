import os
import secrets
import logging as _logging
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = os.getenv("GUILD_ID", "")
def _resolve_db_path(requested: str) -> str:
    """Return requested path if its directory is writable, else fall back to /tmp."""
    try:
        target_dir = os.path.dirname(os.path.abspath(requested)) or "."
        probe = os.path.join(target_dir, ".db_write_probe")
        with open(probe, "w") as f:
            f.write("")
        os.unlink(probe)
        return requested
    except OSError:
        return "/tmp/listings.db"

DB_PATH = _resolve_db_path(os.getenv("DB_PATH", "listings.db"))
DISCORD_ERROR_WEBHOOK = os.getenv("DISCORD_ERROR_WEBHOOK", "")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
if not FLASK_SECRET_KEY:
    FLASK_SECRET_KEY = secrets.token_hex(32)
    _logging.warning(
        "FLASK_SECRET_KEY not set in .env — using a random key. "
        "All sessions will be invalidated on restart. "
        "Set FLASK_SECRET_KEY in .env to persist sessions."
    )
