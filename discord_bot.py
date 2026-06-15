import logging
import requests
from config import DISCORD_TOKEN, GUILD_ID
from scraper import city_to_slug

logger = logging.getLogger(__name__)

BASE = "https://discord.com/api/v10"
HEADERS = {
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "Content-Type": "application/json",
}


def _get_or_create_channel(city: str) -> str:
    channel_name = city_to_slug(city)
    resp = requests.get(f"{BASE}/guilds/{GUILD_ID}/channels", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    for ch in resp.json():
        if ch.get("name") == channel_name and ch.get("type") == 0:
            return ch["id"]
    resp = requests.post(
        f"{BASE}/guilds/{GUILD_ID}/channels",
        headers=HEADERS,
        json={"name": channel_name, "type": 0},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def send_listing(listing: dict) -> bool:
    try:
        channel_id = _get_or_create_channel(listing["city"])
        price_str = f"{int(listing['price']):,}".replace(",", " ") if listing.get("price") is not None else "?"
        area_str = f"{listing['area']:.0f}" if listing.get("area") is not None else "?"
        ppm2_str = f"{int(listing['price_per_m2']):,}".replace(",", " ") if listing.get("price_per_m2") is not None else "?"
        city_display = listing["city"].replace("-", " ").title()
        content = (
            f"🏠 **Nowe ogłoszenie — {city_display}**\n"
            f"📍 {listing['title']}\n"
            f"💰 {price_str} zł  |  📐 {area_str} m²  |  📊 {ppm2_str} zł/m²\n"
            f"🔗 {listing['url']}"
        )
        msg_resp = requests.post(
            f"{BASE}/channels/{channel_id}/messages",
            headers=HEADERS,
            json={"content": content},
            timeout=10,
        )
        msg_resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("send_listing failed for listing %s: %s", listing.get("id"), e)
        return False
