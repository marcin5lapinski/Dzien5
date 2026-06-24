import os
import secrets
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = os.getenv("GUILD_ID", "")
DB_PATH = os.getenv("DB_PATH", "listings.db")
DISCORD_ERROR_WEBHOOK = os.getenv("DISCORD_ERROR_WEBHOOK", "")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
