from flask import Flask, request, jsonify, render_template
from database import init_db, save_listings, mark_sent, get_stats
from scraper import fetch_listings
from discord_bot import send_listing

app = Flask(__name__)


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

    listings = fetch_listings(city, voivodeship)
    new_listings = save_listings(listings)

    discord_sent = 0
    sent_ids = []
    for listing in new_listings:
        if send_listing(listing):
            discord_sent += 1
            sent_ids.append(listing["id"])

    mark_sent(sent_ids)

    return jsonify({
        "fetched": len(listings),
        "new": len(new_listings),
        "discord_sent": discord_sent,
    })


@app.route("/api/stats")
def api_stats():
    city = request.args.get("city") or None
    price_max = request.args.get("price_max", type=float)
    area_min = request.args.get("area_min", type=float)
    return jsonify(get_stats(city, price_max, area_min))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
