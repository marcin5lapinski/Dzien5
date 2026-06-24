import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import currency

SAMPLE_RESPONSE = [
    {
        "table": "A",
        "no": "001/A/NBP/2025",
        "effectiveDate": "2025-01-02",
        "rates": [
            {"currency": "dolar amerykański", "code": "USD", "mid": 4.0812},
            {"currency": "euro", "code": "EUR", "mid": 4.2713},
        ]
    }
]

def make_mock_resp(data):
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status = MagicMock()
    return m


@patch("currency.requests.get")
def test_fetch_returns_rate_dicts(mock_get):
    mock_get.return_value = make_mock_resp(SAMPLE_RESPONSE)
    result = currency.fetch_rates_for_period(
        date(2025, 1, 1), date(2025, 1, 10)
    )
    assert len(result) == 2
    assert result[0]["currency_code"] == "USD"
    assert result[0]["rate"] == 4.0812
    assert result[0]["date"] == "2025-01-02"


@patch("currency.requests.get")
def test_fetch_returns_empty_on_error(mock_get):
    mock_get.side_effect = Exception("timeout")
    result = currency.fetch_rates_for_period(
        date(2025, 1, 1), date(2025, 1, 10)
    )
    assert result == []


@patch("currency.fetch_rates_for_period")
def test_fetch_last_18_months_makes_multiple_calls(mock_fetch):
    mock_fetch.return_value = []
    currency.fetch_rates_last_18_months()
    assert mock_fetch.call_count >= 6


def test_date_chunks_covers_18_months():
    chunks = currency._date_chunks(18)
    start, _ = chunks[0]
    _, end = chunks[-1]
    today = date.today()
    eighteen_months_ago = today.replace(year=today.year - 1, month=today.month - 6) \
        if today.month > 6 \
        else today.replace(year=today.year - 2, month=today.month + 6)
    # start should be roughly 18 months ago (within a few days)
    assert abs((start - eighteen_months_ago).days) <= 5
    assert end >= today - timedelta(days=2)
