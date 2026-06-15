from unittest.mock import patch, MagicMock, call
import requests as req_lib
import discord_bot

LISTING = {
    "id": "abc123",
    "city": "wroclaw",
    "title": "3 pokoje, Śródmieście",
    "price": 750000.0,
    "area": 55.0,
    "price_per_m2": 13636.0,
    "url": "https://www.otodom.pl/pl/oferta/abc123",
}

def make_mock_get(channels):
    mock = MagicMock()
    mock.json.return_value = channels
    mock.raise_for_status = MagicMock()
    return mock

def make_mock_post(channel_id="999"):
    mock = MagicMock()
    mock.json.return_value = {"id": channel_id}
    mock.raise_for_status = MagicMock()
    return mock


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_uses_existing_channel(mock_get, mock_post):
    mock_get.return_value = make_mock_get([
        {"id": "111", "name": "wroclaw", "type": 0}
    ])
    mock_post.return_value = make_mock_post()
    result = discord_bot.send_listing(LISTING)
    assert result is True
    assert mock_post.call_count == 1
    assert "messages" in mock_post.call_args[0][0]


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_creates_channel_when_missing(mock_get, mock_post):
    mock_get.return_value = make_mock_get([])
    mock_post.return_value = make_mock_post("222")
    discord_bot.send_listing(LISTING)
    assert mock_post.call_count == 2
    first_url = mock_post.call_args_list[0][0][0]
    second_url = mock_post.call_args_list[1][0][0]
    assert "channels" in first_url and "messages" not in first_url
    assert "messages" in second_url


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_message_contains_price_and_area(mock_get, mock_post):
    mock_get.return_value = make_mock_get([
        {"id": "111", "name": "wroclaw", "type": 0}
    ])
    mock_post.return_value = make_mock_post()
    discord_bot.send_listing(LISTING)
    content = mock_post.call_args[1]["json"]["content"]
    assert "750" in content
    assert "55" in content
    assert "https://www.otodom.pl" in content


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_returns_false_on_error(mock_get, mock_post):
    mock_get.side_effect = Exception("Network error")
    result = discord_bot.send_listing(LISTING)
    assert result is False


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_channel_name_from_city(mock_get, mock_post):
    mock_get.return_value = make_mock_get([])
    mock_post.return_value = make_mock_post()
    listing_with_spaces = {**LISTING, "city": "nowy sacz"}
    discord_bot.send_listing(listing_with_spaces)
    create_call_json = mock_post.call_args_list[0][1]["json"]
    assert create_call_json["name"] == "nowy-sacz"


@patch("discord_bot.requests.post")
@patch("discord_bot.requests.get")
def test_returns_false_when_message_post_fails(mock_get, mock_post):
    mock_get.return_value = make_mock_get([
        {"id": "111", "name": "wroclaw", "type": 0}
    ])
    error_resp = MagicMock()
    error_resp.raise_for_status.side_effect = req_lib.HTTPError("403 Forbidden")
    mock_post.return_value = error_resp
    result = discord_bot.send_listing(LISTING)
    assert result is False
