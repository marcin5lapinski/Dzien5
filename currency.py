import calendar
import logging
from datetime import date, datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

NBP_URL = "https://api.nbp.pl/api/exchangerates/tables/A/{start}/{end}/?format=json"
MAX_DAYS = 90  # NBP allows max 92 days per request; use 90 for safety


def _date_chunks(months: int) -> list[tuple[date, date]]:
    """Split the last `months` months into chunks of MAX_DAYS days."""
    today = date.today()
    # Go back `months` months (keeping the same day of month)
    year = today.year
    month = today.month - months
    while month <= 0:
        month += 12
        year -= 1
    # Clamp day to valid range for the target month (e.g. Jan 31 - 3 months -> Oct 31 ok, but Feb 31 invalid)
    max_day = calendar.monthrange(year, month)[1]
    day = min(today.day, max_day)
    start = today.replace(year=year, month=month, day=day)

    chunks = []
    current = start
    while current < today:
        chunk_end = min(current + timedelta(days=MAX_DAYS - 1), today)
        chunks.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return chunks


def fetch_rates_for_period(start: date, end: date) -> list[dict]:
    """Fetch all currency rates from NBP for a given date range."""
    url = NBP_URL.format(start=start.isoformat(), end=end.isoformat())
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        tables = resp.json()
        fetched_at = datetime.now(timezone.utc).isoformat()
        result = []
        for table in tables:
            effective_date = table["effectiveDate"]
            for rate in table["rates"]:
                result.append({
                    "currency_code": rate["code"],
                    "currency_name": rate["currency"],
                    "rate": rate["mid"],
                    "date": effective_date,
                    "fetched_at": fetched_at,
                })
        return result
    except Exception as e:
        logger.error("NBP fetch failed for %s–%s: %s", start, end, e)
        return []


NBP_LATEST_URL = "https://api.nbp.pl/api/exchangerates/tables/A/?format=json"


def fetch_current_rates() -> dict:
    """Fetch the latest available NBP rates in a single fast call.

    Returns {code: {rate, currency_name, date}} or {} on error.
    Used as a live fallback when the database is empty (e.g. cold serverless start).
    """
    try:
        resp = requests.get(NBP_LATEST_URL, timeout=5)
        resp.raise_for_status()
        result = {}
        for table in resp.json():
            date_str = table.get("effectiveDate", "")
            for entry in table.get("rates", []):
                result[entry["code"]] = {
                    "rate": entry["mid"],
                    "currency_name": entry["currency"],
                    "date": date_str,
                }
        return result
    except Exception as e:
        logger.error("NBP current rates fetch failed: %s", e)
        return {}


def fetch_rates_last_18_months() -> list[dict]:
    """Fetch all currency rates for the last 18 months."""
    all_rates = []
    for start, end in _date_chunks(18):
        rates = fetch_rates_for_period(start, end)
        all_rates.extend(rates)
        logger.info("Fetched %d rates for %s–%s", len(rates), start, end)
    return all_rates
