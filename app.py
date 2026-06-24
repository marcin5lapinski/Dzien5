import base64
import io
import logging
import os
import secrets
import uuid

import qrcode
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request, session

from config import FLASK_SECRET_KEY
from currency import fetch_rates_last_18_months
from database import (
    get_latest_rates, get_listing, get_notes, get_price_history, get_stats,
    get_tags, get_unsent, init_db, mark_sent, record_price_if_changed,
    save_currency_rates, save_listings, save_note, save_tag,
    search_listings_by_note,
)
from discord_bot import send_error_to_discord, send_listing
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
CORS(app)

# In-memory QR token store: {token: session_id}
_qr_tokens: dict[str, str] = {}

try:
    init_db()
except Exception as _e:
    logger.warning("init_db failed: %s", _e)


def _get_session_id() -> str:
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


def do_fetch(city: str, voivodeship: str) -> dict:
    listings = fetch_listings(city, voivodeship)
    new_listings = save_listings(listings)

    # Record price history for all fetched listings
    for listing in listings:
        record_price_if_changed(listing["id"], listing.get("price"), listing.get("price_per_m2"))

    discord_sent = 0
    sent_ids = []
    for listing in new_listings:
        if send_listing(listing):
            discord_sent += 1
            sent_ids.append(listing["id"])
        else:
            send_error_to_discord("Discord", f"Nie udało się wysłać ogłoszenia {listing['id']} na Discord")
    mark_sent(sent_ids)

    unsent = get_unsent(city.lower())
    retry_ids = []
    for listing in unsent:
        if listing["id"] not in sent_ids:
            if send_listing(listing):
                retry_ids.append(listing["id"])
    mark_sent(retry_ids)
    discord_sent += len(retry_ids)

    return {"fetched": len(listings), "new": len(new_listings), "discord_sent": discord_sent}


def _daily_fetch_rates():
    logger.info("Daily currency rate fetch starting...")
    try:
        rates = fetch_rates_last_18_months()
        count = save_currency_rates(rates)
        logger.info("Daily fetch: inserted %d new rates", count)
    except Exception as e:
        logger.error("Daily rate fetch failed: %s", e)
        send_error_to_discord("NBP kursy walut", str(e))


# Start scheduler + Discord gateway only in the worker process
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    from scraper import fetch_listings
    from discord_gateway import start_gateway
    start_gateway(do_fetch)

    scheduler = BackgroundScheduler()
    scheduler.add_job(_daily_fetch_rates, "cron", hour=3, minute=0)
    scheduler.start()
    logger.info("APScheduler started — daily rate fetch at 03:00")
else:
    from scraper import fetch_listings


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    _get_session_id()
    return render_template("index.html")


@app.route("/listing/<listing_id>")
def listing_detail(listing_id):
    _get_session_id()
    return render_template("listing.html", listing_id=listing_id)


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})


@app.route("/fetch", methods=["POST"])
def api_fetch():
    data = request.get_json(silent=True) or {}
    city = (data.get("city") or "").strip()
    voivodeship = (data.get("voivodeship") or "").strip()
    if not city or not voivodeship:
        return jsonify({"error": "city and voivodeship required"}), 400
    try:
        return jsonify(do_fetch(city, voivodeship))
    except Exception as e:
        send_error_to_discord("Fetch ogłoszeń", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/stats")
def api_stats():
    city = request.args.get("city") or None
    price_max = request.args.get("price_max", type=float)
    area_min = request.args.get("area_min", type=float)
    try:
        return jsonify(get_stats(city, price_max, area_min))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/listing/<listing_id>")
def api_listing(listing_id):
    listing = get_listing(listing_id)
    if not listing:
        return jsonify({"error": "not found"}), 404
    return jsonify(listing)


@app.route("/api/listing/<listing_id>/price-history")
def api_price_history(listing_id):
    history = get_price_history(listing_id)
    rates = get_latest_rates()
    # Add converted prices for EUR and USD
    for entry in history:
        price = entry.get("price")
        if price:
            eur_rate = rates.get("EUR", {}).get("rate")
            usd_rate = rates.get("USD", {}).get("rate")
            entry["price_eur"] = round(price / eur_rate, 2) if eur_rate else None
            entry["price_usd"] = round(price / usd_rate, 2) if usd_rate else None
        else:
            entry["price_eur"] = None
            entry["price_usd"] = None
    return jsonify(history)


@app.route("/api/listing/<listing_id>/notes", methods=["GET"])
def api_get_notes(listing_id):
    sid = _get_session_id()
    return jsonify(get_notes(listing_id, sid))


@app.route("/api/listing/<listing_id>/notes", methods=["POST"])
def api_add_note(listing_id):
    sid = _get_session_id()
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content required"}), 400
    note = save_note(listing_id, sid, content)
    return jsonify(note), 201


@app.route("/api/listing/<listing_id>/tags", methods=["GET"])
def api_get_tags(listing_id):
    sid = _get_session_id()
    return jsonify(get_tags(listing_id, sid))


@app.route("/api/listing/<listing_id>/tags", methods=["POST"])
def api_add_tag(listing_id):
    sid = _get_session_id()
    data = request.get_json(silent=True) or {}
    tag = (data.get("tag") or "").strip()
    if not tag:
        return jsonify({"error": "tag required"}), 400
    return jsonify(save_tag(listing_id, sid, tag)), 201


@app.route("/api/rates")
def api_rates():
    return jsonify(get_latest_rates())


@app.route("/api/fetch-rates", methods=["POST"])
def api_fetch_rates():
    try:
        rates = fetch_rates_last_18_months()
        count = save_currency_rates(rates)
        return jsonify({"fetched": len(rates), "inserted": count})
    except Exception as e:
        send_error_to_discord("NBP kursy walut", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/api/search-notes")
def api_search_notes():
    sid = _get_session_id()
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify([])
    return jsonify(search_listings_by_note(query, sid))


# ── QR Login ───────────────────────────────────────────────────────────────────

@app.route("/qr-auth")
def qr_auth():
    """Generate a QR code that transfers the current session to another device."""
    sid = _get_session_id()
    token = secrets.token_urlsafe(32)
    _qr_tokens[token] = sid

    base_url = request.host_url.rstrip("/")
    login_url = f"{base_url}/qr-login/{token}"

    img = qrcode.make(login_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return render_template("qr_auth.html", qr_b64=b64, login_url=login_url)


@app.route("/qr-login/<token>")
def qr_login(token):
    """Phone opens this URL after scanning QR — gets the same session_id."""
    sid = _qr_tokens.pop(token, None)
    if not sid:
        return jsonify({"error": "Token nieważny lub już użyty"}), 400
    session["session_id"] = sid
    return render_template("qr_success.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
