# Otodom Tracker — Design Spec

**Data:** 2026-06-15  
**Projekt:** ALX Dzień 5b  
**Stack:** Python Flask · SQLite · requests + BeautifulSoup · Discord HTTP API · Chart.js

---

## 1. Cel

Lokalna aplikacja webowa, która:
- pobiera 10 najnowszych ofert mieszkań z otodom.pl dla wybranego miasta
- zapisuje je do lokalnej bazy SQLite (bez duplikatów)
- wysyła nowe oferty na kanał Discord nazwany miastem (tworzy kanał jeśli nie istnieje)
- wyświetla statystyki i wykresy na dashboardzie w stylu Dzikiego Zachodu

---

## 2. Architektura

Jeden serwer Flask serwujący zarówno API jak i frontend (single-page).

```
otodom-tracker/
├── app.py              # Flask — endpointy API + serwowanie index.html
├── scraper.py          # pobieranie ofert (requests + BeautifulSoup, fallback Playwright)
├── database.py         # init SQLite, zapis ofert, zapytania dla dashboardu
├── discord_bot.py      # wysyłanie wiadomości i tworzenie kanałów przez Discord HTTP API
├── config.py           # wczytywanie zmiennych z .env
├── templates/
│   └── index.html      # formularz + dashboard (Wild West theme) + Chart.js
├── .env                # DISCORD_TOKEN, GUILD_ID (nie w repozytorium)
├── requirements.txt
└── listings.db         # tworzony automatycznie przy pierwszym uruchomieniu
```

---

## 3. Baza danych (SQLite)

Tabela `listings`:

| Kolumna | Typ | Opis |
|---|---|---|
| `id` | TEXT PRIMARY KEY | unikalny ID z otodom — zapobiega duplikatom |
| `city` | TEXT | miasto (lowercase) |
| `title` | TEXT | tytuł ogłoszenia |
| `price` | REAL | cena w zł |
| `area` | REAL | powierzchnia w m² |
| `price_per_m2` | REAL | wyliczane przy zapisie |
| `url` | TEXT | link do ogłoszenia |
| `fetched_at` | TEXT | ISO timestamp pobrania |
| `sent_to_discord` | INTEGER | 0 = nie wysłano, 1 = wysłano |

Zapis przez `INSERT OR IGNORE` — duplikaty są cicho odrzucane przez PRIMARY KEY.

---

## 4. API Endpoints

### `POST /api/fetch`
**Body:** `{ "city": "Wrocław", "voivodeship": "dolnośląskie" }`

Kolejność działania:
1. `scraper.py` → pobiera 10 najnowszych ofert z otodom
2. `database.py` → `INSERT OR IGNORE` każdej oferty, zlicza ile zostało wstawionych (nowe)
3. `discord_bot.py` → dla każdej nowej oferty wysyła wiadomość na kanał `#{city_lowercase}`; jeśli kanał nie istnieje — tworzy go
4. Oznacza nowe oferty `sent_to_discord = 1`

**Odpowiedź:** `{ "fetched": 10, "new": 3, "discord_sent": 3 }`

### `GET /api/stats`
**Query params:** `city`, `price_max`, `area_min`

**Odpowiedź:**
```json
{
  "total": 10,
  "avg_price": 720000,
  "avg_price_per_m2": 13900,
  "avg_area": 52,
  "price_histogram": [[400000, 2], [600000, 4], ...],
  "area_histogram": [[25, 1], [50, 5], ...],
  "listings": [{ "id": "...", "title": "...", "price": ..., ... }]
}
```

### `GET /api/listings`
Lista wszystkich ofert z bazy (opcjonalne filtry jak w /api/stats).

### `GET /`
Serwuje `templates/index.html`.

---

## 5. Scraper (scraper.py)

- **Podejście:** `requests` z nagłówkami User-Agent + `BeautifulSoup` do parsowania HTML
- **URL wzorzec:** `https://www.otodom.pl/pl/oferty/sprzedaz/mieszkanie/{voivodeship}/{city}?limit=10&by=LATEST`
- **Fallback:** jeśli requests dostanie 403/captcha → loguje błąd i zwraca pustą listę (Playwright jako opcjonalne rozszerzenie)
- **Parsowane pola:** id (z URL lub atrybutu data), title, price, area, url

---

## 6. Discord (discord_bot.py)

Używa Discord HTTP API bezpośrednio przez `requests` — bez gateway, bez `discord.py`, bez intentów. Bot tylko wysyła (nie nasłuchuje eventów).

**Konfiguracja:**
- `DISCORD_TOKEN` — bot token z Developer Portal
- `GUILD_ID` — ID serwera Discord

**Logika kanału:**
1. `GET /guilds/{guild_id}/channels` — pobiera listę kanałów
2. Szuka kanału o nazwie `{city.lower().replace(" ", "-")}`
3. Jeśli nie istnieje → `POST /guilds/{guild_id}/channels` z `type: 0` (text channel)
4. `POST /channels/{channel_id}/messages` — wysyła embed z ofertą

**Format wiadomości:**
```
🏠 Nowe ogłoszenie — Wrocław
📍 Tytuł oferty
💰 720 000 zł  |  📐 52 m²  |  📊 13 846 zł/m²
🔗 https://www.otodom.pl/...
```

---

## 7. Frontend (templates/index.html)

**Styl:** Wild West — czcionka Rye (Google Fonts), pergaminowe tło, brązowo-bursztynowa paleta barw.

**Sekcje (od góry):**
1. **Header** — logo "Otodom Tracker ★ Dziki Zachód Nieruchomości ★"
2. **Plakat WANTED** — formularz: pole Miasto, dropdown Województwo, przycisk "🔫 Szukaj!", komunikat statusu po pobraniu
3. **Saloon — Filtry** — dropdowny: Miasto, Cena max, Pow. min + przycisk "Filtruj"
4. **Odznaki KPI** — 4 kafelki w stylu odznak szeryfa: Oferty, Śr. cena, Cena/m², Śr. pow.
5. **Wykresy** — 2 histogramy Chart.js (Rozkład Cen, Rozkład Metraży)
6. **Tablica Ogłoszeń Szeryfatu** — tabela: Tytuł, Miasto, Cena, m², zł/m², Link

**Przepływ JS (zero page reload):**
1. Klik "Szukaj" → `fetch POST /api/fetch` → pokaż status badge
2. → `fetch GET /api/stats?filters...` → zaktualizuj KPI + wykresy + tabelę

---

## 8. Konfiguracja (.env)

```
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here
FLASK_PORT=5000
```

---

## 9. Co użytkownik musi zrobić ręcznie (jednorazowo)

1. Utwórz serwer Discord (jeśli nie masz własnego)
2. Wejdź na [discord.com/developers/applications](https://discord.com/developers/applications) → "New Application" → zakładka "Bot" → skopiuj Token
3. W OAuth2 → URL Generator: scope `bot`, uprawnienia `Send Messages` + `Manage Channels` → otwórz URL → dodaj bota do serwera
4. Prawym klikiem na ikonę serwera → "Kopiuj ID serwera" (Guild ID)
5. Wstaw Token i Guild ID do pliku `.env`

---

## 10. Uruchomienie

```bash
pip install -r requirements.txt
python app.py
# → http://localhost:5000
```

---

## 11. Zależności (requirements.txt)

```
flask
requests
beautifulsoup4
python-dotenv
```
