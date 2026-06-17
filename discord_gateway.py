import json
import logging
import threading
import time

import requests
import websocket  # websocket-client

from config import DISCORD_TOKEN, GUILD_ID

logger = logging.getLogger(__name__)

BASE = "https://discord.com/api/v10"
HEADERS = {
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "Content-Type": "application/json",
}

_COMMAND_NAME = "pobierz"


def _get_app_id() -> str:
    r = requests.get(f"{BASE}/applications/@me", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()["id"]


def _register_command(app_id: str):
    cmd = {
        "name": _COMMAND_NAME,
        "description": "Pobierz nowe oferty z otodom dla danego miasta",
        "options": [
            {
                "name": "miasto",
                "description": "Nazwa miasta (np. Wrocław)",
                "type": 3,
                "required": True,
            },
            {
                "name": "wojewodztwo",
                "description": "Województwo — opcjonalne dla znanych miast",
                "type": 3,
                "required": False,
            },
        ],
    }
    r = requests.post(
        f"{BASE}/applications/{app_id}/guilds/{GUILD_ID}/commands",
        headers=HEADERS,
        json=cmd,
        timeout=10,
    )
    r.raise_for_status()
    logger.info("Registered /%s guild command (id=%s)", _COMMAND_NAME, r.json().get("id"))


def _ack(interaction_id: str, token: str):
    """Send deferred response to avoid Discord's 3-second timeout."""
    requests.post(
        f"{BASE}/interactions/{interaction_id}/{token}/callback",
        headers=HEADERS,
        json={"type": 5},
        timeout=5,
    )


def _edit(app_id: str, token: str, content: str):
    requests.patch(
        f"{BASE}/webhooks/{app_id}/{token}/messages/@original",
        headers=HEADERS,
        json={"content": content},
        timeout=10,
    )


def _handle_interaction(interaction: dict, fetch_callback):
    token = interaction["token"]
    app_id = interaction["application_id"]
    options = {o["name"]: o["value"] for o in interaction["data"].get("options", [])}
    city = options.get("miasto", "").strip()
    voivodeship = options.get("wojewodztwo", "").strip()

    if not voivodeship:
        from scraper import lookup_voivodeship
        voivodeship = lookup_voivodeship(city)
        if not voivodeship:
            _edit(app_id, token,
                  f"❌ Nie znam województwa dla **{city}**. "
                  f"Użyj parametru `wojewodztwo`, np. `/pobierz miasto:{city} wojewodztwo:dolnośląskie`.")
            return

    try:
        result = fetch_callback(city, voivodeship)
        content = (
            f"✅ **{city.title()}** — pobrano {result['fetched']} ofert "
            f"· {result['new']} nowych · {result['discord_sent']} wysłano na Discord"
        )
    except Exception as e:
        logger.exception("fetch_callback failed for %s", city)
        content = f"❌ Błąd podczas pobierania ofert dla **{city}**: {e}"

    _edit(app_id, token, content)


class _GatewayClient:
    def __init__(self, fetch_callback):
        self._fetch_callback = fetch_callback
        self._ws = None
        self._sequence = None
        self._heartbeat_interval = None
        self._running = False

    def run(self):
        r = requests.get(f"{BASE}/gateway/bot", headers=HEADERS, timeout=10)
        r.raise_for_status()
        url = r.json()["url"] + "?v=10&encoding=json"
        self._running = True
        self._ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._ws.run_forever()
        self._running = False

    def _on_open(self, ws):
        logger.info("Discord gateway connected")

    def _on_message(self, ws, raw):
        msg = json.loads(raw)
        op = msg["op"]
        if msg.get("s"):
            self._sequence = msg["s"]

        if op == 10:  # Hello
            self._heartbeat_interval = msg["d"]["heartbeat_interval"] / 1000
            threading.Thread(target=self._heartbeat_loop, daemon=True).start()
            ws.send(json.dumps({
                "op": 2,
                "d": {
                    "token": DISCORD_TOKEN,
                    "intents": 0,
                    "properties": {"os": "windows", "browser": "otodom-bot", "device": "otodom-bot"},
                },
            }))
        elif op == 0 and msg.get("t") == "INTERACTION_CREATE":
            self._dispatch(msg["d"])

    def _on_error(self, ws, error):
        logger.error("Discord gateway error: %s", error)

    def _on_close(self, ws, code, msg):
        logger.warning("Discord gateway closed (code=%s)", code)
        self._running = False

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(self._heartbeat_interval)
            if self._ws and self._running:
                try:
                    self._ws.send(json.dumps({"op": 1, "d": self._sequence}))
                except Exception:
                    break

    def _dispatch(self, interaction: dict):
        if interaction.get("type") != 2:
            return
        if interaction["data"].get("name") != _COMMAND_NAME:
            return
        _ack(interaction["id"], interaction["token"])
        threading.Thread(
            target=_handle_interaction,
            args=(interaction, self._fetch_callback),
            daemon=True,
        ).start()


def start_gateway(fetch_callback):
    """Register /pobierz slash command and start gateway listener in background."""
    try:
        app_id = _get_app_id()
        _register_command(app_id)
    except Exception as e:
        logger.error("Failed to register Discord command: %s", e)
        return

    def _run():
        while True:
            try:
                _GatewayClient(fetch_callback).run()
            except Exception as e:
                logger.error("Gateway crashed: %s", e)
            time.sleep(5)
            logger.info("Reconnecting to Discord gateway...")

    threading.Thread(target=_run, daemon=True).start()
    logger.info("Discord gateway thread started")
