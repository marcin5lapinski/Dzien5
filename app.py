import logging
import os

from flask import Flask, request, jsonify, render_template

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
from database import init_db, save_listings, mark_sent, get_stats, get_unsent
from scraper import fetch_listings
from discord_bot import send_listing

app = Flask(__name__)
init_db()  # idempotent — CREATE TABLE IF NOT EXISTS


def do_fetch(city: str, voivodeship: str) -> dict:
    """Fetch listings, save to DB, send new ones to Discord. Returns summary dict."""
    listings = fetch_listings(city, voivodeship)
    new_listings = save_listings(listings)

    discord_sent = 0
    sent_ids = []
    for listing in new_listings:
        if send_listing(listing):
            discord_sent += 1
            sent_ids.append(listing["id"])
    mark_sent(sent_ids)

    # Retry previously unsent listings for this city
    unsent = get_unsent(city.lower())
    retry_ids = []
    for listing in unsent:
        if listing["id"] not in sent_ids:
            if send_listing(listing):
                retry_ids.append(listing["id"])
    mark_sent(retry_ids)
    discord_sent += len(retry_ids)

    return {"fetched": len(listings), "new": len(new_listings), "discord_sent": discord_sent}


# Start gateway only in the worker process (not in Flask's reloader watcher)
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    from discord_gateway import start_gateway
    start_gateway(do_fetch)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    data = request.get_json(silent=True) or {}
    city = (data.get("city") or "").strip()
    voivodeship = (data.get("voivodeship") or "").strip()
    if not city or not voivodeship:
        return jsonify({"error": "city and voivodeship required"}), 400

    try:
        return jsonify(do_fetch(city, voivodeship))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    city = request.args.get("city") or None
    price_max = request.args.get("price_max", type=float)
    area_min = request.args.get("area_min", type=float)
    try:
        return jsonify(get_stats(city, price_max, area_min))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
