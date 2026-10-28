# AI Smart Deal Predictor

A premium, dark-themed shopping intelligence app built with **Python and
Streamlit**. It combines recorded price history, live marketplace quotes,
transparent deal scoring, a 7-day regression estimate, offer comparison,
target-price watchlists, catalog insights, and a floating **AI Shopping
Copilot**.

The copilot is deliberately grounded: every price, seller, coupon, observation,
and prediction it discusses comes from the app's own database and Python
calculations. It never invents marketplace data, and it says so when data is
missing.

> **Two kinds of data, always labelled:**
>
> - **Live quotes** are the last successful reading of a specific public product
>   page. They can be stale, partial, out of stock, or unavailable.
> - **Demo records** are a deterministic synthetic catalog. They are sample data,
>   never live marketplace prices.

---

## Highlights

- **Live marketplace quotes** — import a product-detail URL from Amazon.in,
  Flipkart, or another retailer with readable product metadata. One product can
  have several source URLs; its current price is the lowest in-stock quote.
- **Ten focused sections** — Dashboard, Deal finder, Products, Compare, Live
  quotes, Watchlist, Alerts, Purchases, Insights, and How it works.
- **Persistent alert inbox** — target levels, price drops, stock changes, and
  quote problems are saved as deduplicated alerts you can read or dismiss. The
  same event never spams the inbox twice.
- **Purchase tracking** — save what you actually paid for a product and compare it
  with the latest recorded quote. Purchase records are user-provided facts, never
  treated as marketplace prices or resale values.
- **Shareable deep links** — every page, product analysis, and comparison has a
  URL you can send. Opening the link restores the same view in a new session.
- **Stale-only refresh** — refresh just the live quotes that need a check, so a
  fresh quote is never re-scraped unnecessarily.
- **Floating copilot** — the bottom-right launcher opens a responsive right-side
  drawer without navigating away from the page.
- **Context-aware answers** — the open product is attached automatically. The
  copilot can also recognise product names mentioned in a question.
- **Grounded facts, explicit estimates** — live quotes, demo records, app
  calculations, and forecasts are kept distinct in both the UI and the answers.
- **Local-first fallback** — without an API key, the copilot still answers from
  deterministic Python analysis. With a key, the configured model writes the
  explanation; if the request fails, the app clearly labels the built-in answer.
- **Real watchlist actions** — commands such as `set target at ₹8,500` update the
  watchlist directly in Python. The model is never trusted to claim that a write
  happened.
- **Premium responsive UI** — purple/blue accents, rounded cards, a mobile
  full-screen drawer, scrollable chat history, quick prompts, and a persistent
  composer.
- **Offline test suite** — 94 tests with mocked network/AI calls, plus optional
  Playwright browser smoke tests for the panel and failure states.

---

## Quick start

### Windows PowerShell

```powershell
cd "C:\Users\Vindhya Vasini\OneDrive\Documents\PyProject"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

Copy-Item .env.example .env
# Edit .env and add OPENROUTER_API_KEY if you want AI-written explanations.

.\.venv\Scripts\streamlit.exe run app.py
```

If PowerShell blocks activation, call the interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
streamlit run app.py
```

Open <http://localhost:8501>. The SQLite database is created and seeded
automatically on first launch at `data/shopping.db`.

**Requirements:** Python 3.11+ (tested on Python 3.14), Streamlit 1.66+.
The runtime dependencies are in `requirements.txt`; `requirements-dev.txt` adds
pytest and Playwright. Live quote parsing uses BeautifulSoup with Python's
built-in `html.parser`.

---

## The ten sections

| Section | What it does |
|---|---|
| **Dashboard** | Catalog metrics, alert inbox summary, featured deal, category pulse, price-drop radar, strongest deals, and live quote health. |
| **Deal finder** | Filter by budget, category, data source, minimum deal score, and "below recorded average"; sort by score, discount, saving, price, or trend. |
| **Products** | Search and filter the catalog; open a product for history, forecast, score breakdown, offers or live quotes, sources, target form, purchase record, and a shareable link. |
| **Compare** | Put two or three products side by side with a comparison table, recorded price paths, summary cards, and a shareable comparison link. |
| **Live quotes** | Import a product page, add or remove sources, refresh one product, all live products, or only stale quotes; inspect quote health, or remove an imported live product. |
| **Watchlist** | Review active targets, reached targets, the gap to each target, and update or remove a target. |
| **Alerts** | Persistent inbox for reached targets, price drops, stock changes, and quote problems. Filter, mark read, dismiss, or clear dismissed alerts. |
| **Purchases** | Record what you paid for a product, compare it with the latest recorded quote, and see totals. Purchase records are your own facts, not quotes. |
| **Insights** | Category strength, falling prices, forecast outlook, budget map, and observation/offer counts. |
| **How it works** | Explains deal scores, forecasts, data labels, live quote rules, and how to use the copilot. |

---

## Live marketplace quotes

### Import a product

1. Open **Live quotes**.
2. Paste the address-bar URL of **one product**, not a search, category, store,
   cart, or wishlist page.
   - Amazon.in product URLs contain `/dp/`.
   - Flipkart product URLs contain `/p/`.
   - Other retailers are accepted when the page exposes JSON-LD, microdata, or
     OpenGraph product metadata.
3. Optionally add your own label and choose a category.
4. Press **Import live quote**.

The importer records only what the page actually shows:

- product title, brand, description, and image when available;
- listed price and currency;
- seller when available;
- MRP/list price only when the same page shows one;
- availability when it can be read.

It does **not** invent a coupon, delivery fee, seller, MRP, discount,
availability, or history. If a detail is missing, it stays missing and the UI
says so. Quotes must be in **INR**; other currencies are rejected with an
explanation rather than converted.

### Multiple sources and the current price

A live product can have more than one source URL, for example an Amazon.in page
and a Flipkart page for the same item. Each source keeps its own last quote.
The product's current price is the **lowest in-stock live quote across its
attached sources**. MRP is taken from the same source as that winning quote.

### Refresh behavior

- A successful refresh replaces that source's last quote.
- The app records **one live observation per product per day**. A second
  successful refresh on the same day replaces that day's point instead of
  creating duplicates.
- A failed refresh keeps the last successful quote, records the error, and marks
  the quote stale. It does **not** create a new price point.
- If every attached source is out of stock, no new history point is recorded.
- Quotes older than the freshness window (24 hours by default) are labelled
  **Stale quote** even if the last check succeeded.

### Removing a live product

Open the product inside **Live quotes** and use **Remove this live product**. The
action requires an explicit confirmation checkbox and removes:

- the product row;
- its source URLs;
- its recorded live quotes and price history;
- any watchlist target attached to it.

Demo products are protected and cannot be removed this way. Removing a live
product cannot be undone; re-import the product page to start a fresh live
history.

### Access rules and limitations

- The app respects `robots.txt`, throttles requests per host, and validates URLs
  to block local-network/SSRF targets.
- It never bypasses CAPTCHAs, logins, paywalls, or anti-bot controls. Blocked
  pages are reported as an error.
- Retailer pages can change structure or render prices only with JavaScript.
  Such pages fail cleanly with **price not found**; the app does not guess.
- Automated access may be restricted by a retailer's terms of service. Use
  official APIs, affiliate feeds, or permission from the retailer for production
  or commercial use. This project is a demonstration, not a scraping service.

### Recorded demo quotes

Streamlit Community Cloud wipes local files whenever an app sleeps or
redeploys, so a quote imported through the UI would not survive until a later
presentation. On startup, the app re-attaches twenty verified readings captured
from real Amazon.in and Reliance Digital product pages:

- the price, seller, availability, and timestamp are exactly what the page
  showed when it was read;
- the seed currently covers two Amazon.in quotes and eighteen Reliance Digital
  products across audio, phones, laptops, TVs, and refrigerators;
- nothing is synthesised, and no coupon, MRP, or delivery fee is invented;
- normal freshness rules apply, so an old reading is labelled **stale** rather
  than presented as current;
- the sources stay fully refreshable and removable in **Live quotes**.

Set `SEED_LIVE_DEMO=false` to disable this startup seed. The recorded entries
live in `smartdeal/live/seed.py`.

### Live quote statuses

| Status | Meaning |
|---|---|
| **Live** | The last check succeeded and the quote is within the freshness window. |
| **Partial live** | Some attached sources succeeded while others need attention. |
| **Stale quote** | The last successful quote is older than the freshness window. |
| **Live fetch failed** | The latest check failed; the last successful quote is kept and labelled. |
| **Out of stock** | All attached sources currently show out of stock. |
| **No live sources** | The live product has no source URLs attached. |

---

## Secure model setup

The API key is **server-side only**:

- It is read from the Python process environment, optionally loaded from `.env`
  by `python-dotenv`.
- It is never rendered in the browser, written to SQLite, included in the prompt,
  or returned in an answer.
- Error messages and model output are sanitised before display; the key is
  replaced with `[redacted]` if it ever appears.
- The browser never calls the model provider directly.

1. Copy the template:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Set your key in `.env`:

   ```dotenv
   OPENROUTER_API_KEY=sk-or-v1-your-own-key
   OPENROUTER_MODEL=openrouter/auto
   OPENROUTER_SITE_URL=http://localhost:8501
   OPENROUTER_APP_NAME=AI Smart Deal Predictor
   ```

3. Restart Streamlit. The sidebar changes from **Guided analysis** to
   **Smart explanations**.

`openrouter/auto` is the default router; set `OPENROUTER_MODEL` to any exact
model ID available in your account if you prefer a specific model.

### Configuration reference

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENROUTER_API_KEY` | For AI | none | Server-side credential. Placeholder values are treated as missing. |
| `OPENROUTER_MODEL` | No | `openrouter/auto` | Exact model ID sent to the provider. |
| `OPENROUTER_SITE_URL` | No | `http://localhost:8501` | Optional request metadata. |
| `OPENROUTER_APP_NAME` | No | `AI Smart Deal Predictor` | Optional request metadata. |
| `OPENROUTER_API_URL` | No | OpenRouter chat-completions URL | Override for a proxy or local test server. |
| `AI_COPILOT_TIMEOUT` | No | `45` | AI read timeout in seconds, clamped to 5–120. |
| `SHOPPING_DB_PATH` | No | `data/shopping.db` | Override the SQLite file location. |
| `LIVE_SCRAPER_TIMEOUT` | No | `15` | Live page request timeout in seconds, clamped to 5–60. |
| `LIVE_SCRAPER_MIN_INTERVAL` | No | `2.0` | Minimum delay between requests to the same host, clamped to 0–60 seconds. |
| `LIVE_SCRAPER_MAX_BYTES` | No | `3000000` | Maximum HTML response size, clamped to 100 KB–10 MB. |
| `LIVE_QUOTE_STALE_HOURS` | No | `24` | Age at which a quote is labelled stale, clamped to 1–168 hours. |
| `LIVE_SCRAPER_CHECK_ROBOTS` | No | `1` | Respect `robots.txt`. Set to `0` only for controlled testing. |
| `LIVE_SCRAPER_USER_AGENT` | No | app default | Optional descriptive user agent. |

`.env` is gitignored. For deployment, use the platform's secret manager or
environment variables rather than committing a file.

---

## Using the copilot

1. Open a product from **Products** to attach it to the copilot context.
2. Press **✦ Copilot** at the bottom-right.
3. Ask a question, or use one of the six quick prompts:

   - `Is this a good deal?`
   - `Should I buy now or wait?`
   - `Explain the price history.`
   - `Find the best available offer.`
   - `Help me save money.`
   - `Compare products.`

4. Press **Enter** to send; **Shift+Enter** inserts a newline.
5. Use **Reset** to clear the current session's chat, **Clear** beside the context
   card to detach the product, and **×** to close the drawer. Reopening the panel
   keeps the current session's messages.

The empty state heading is exactly **“Your Personal Shopping Copilot”**.

### What the copilot can discuss

- The current recorded or live price versus the product's own recorded low,
  average, and high.
- The four deal-score components and the resulting 0–100 score.
- The latest recorded observations and the 30-day trend.
- The 7-day linear-regression estimate, its uncertainty range, and confidence.
- Live marketplace quotes, their retailer, availability, status, and last-checked
  time — without pretending a stale quote is current.
- Demo seller offers, recorded coupons, delivery fees, and effective totals.
- Target-price suggestions and the gap to a target.
- Navigation help for all ten sections.
- Budget questions such as “What is the best deal under ₹20,000?”

### What it will not do

- Invent a price, seller, coupon, observation, MRP, availability, or prediction.
- Treat demo rows as live marketplace prices.
- Treat a stale or failed live quote as a current price.
- Claim to have checked an external marketplace.
- Guarantee a future price or promise that a target will be reached.
- Claim that a watchlist was updated unless the Python action actually wrote it.

If the user asks a product-specific question without a product in context, the
copilot asks which product to inspect rather than guessing. If a product has no
history or offers, it says so explicitly.

---

## How the copilot is grounded

```
User question
     │
     ▼
build_shopping_context()  ── products, live sources, history, offers, watchlist
     │                       + analytics.py snapshots and forecasts
     ├── watchlist command? ── Python writes the database, returns verified action
     │
     ├── no API key? ──────── deterministic built-in answer
     │
     └── API key present? ─── model-written explanation
                               │
                               ├── success ── "AI-written explanation" badge
                               └── failure ── built-in answer + warning badge
```

The system prompt in `smartdeal/copilot/service.py` contains explicit grounding
rules. The shopping context is serialised as JSON and contains:

- The selected product's recorded facts, live status, calculations, offers, and
  watchlist.
- Any other products explicitly mentioned in the question.
- A compact catalog overview and top deals.
- A description of the app's pages for navigation help.
- A provenance note separating live-imported products from demo rows.

The model receives **no** API key, environment variables, or raw database
connection. The app performs all arithmetic in Python.

### Source badges

| Badge | Meaning |
|---|---|
| **AI-written explanation · grounded in app data** | The answer text came from a successful model response. |
| **Built-in analysis · no external service** | No key was configured; the deterministic Python answer was used. |
| **Built-in analysis · smart explanation unavailable** | The model request failed; the app shows the built-in answer and a warning. It never presents this as model-written. |
| **Watchlist updated · verified in app** | Python performed the database write and reports the result. |

### Failure handling

- **Missing key** — built-in analysis with an informational notice; no network call.
- **401/403** — credentials message; built-in fallback.
- **402** — credits message; built-in fallback.
- **429** — one retry with `Retry-After` support, then a rate-limit warning and
  built-in fallback.
- **5xx** — one retry, then a provider warning and built-in fallback.
- **Timeout / network** — clear message and built-in fallback.
- **Malformed response** — no model answer is used; built-in fallback.
- **Unexpected app error** — a safe error answer; the shopping pages remain usable.

The chat shows a short, user-facing notice for these cases. Provider names,
credential details, and configuration instructions stay in server-side error
classification rather than appearing in the website UI.

---

## Data, calculations, and limitations

### Demo dataset

`smartdeal/seed.py` creates a deterministic synthetic catalog:

- **40 products** across audio, wearables, laptops, desktops, monitors, tablets,
  smartphones, cameras, gaming, kitchen, home, fitness, and accessories.
- **120 daily price observations per product** (4,800 total).
- **4 seller offers per product** with listed prices, coupons, delivery fees, and
  stock status.
- **4 seeded watchlist targets** in a fresh database.

Existing databases are extended with any missing demo products on startup. User
watchlists, live products, and other edits are not overwritten. Delete
`data/shopping.db` to regenerate the original demo state on the next start.

Live-imported products are kept separate from demo products. A live quote cannot
be attached to a demo row, so synthetic history and real marketplace quotes are
never mixed.

### Deal score (0–100)

| Component | Weight | Meaning |
|---|---:|---|
| Price position | 40% | Where the current price sits between the product's recorded low and high. |
| Discount | 25% | Saving against the product's detected MRP. Missing MRP earns no discount credit rather than an invented saving. |
| Recent trend | 20% | Direction of the latest 30 observations. |
| Best offer | 15% | Effective total after recorded coupon and delivery (demo), or the live quote position. |

Labels: **Excellent deal** ≥ 78, **Good deal** ≥ 62, **Fair deal** ≥ 45,
**Wait for a better price** < 45.

The score compares a product with its own history. It is not a cross-product
quality rating and not financial advice.

### Effective offer total

For demo offers:

```
effective total = max(0, listed price − recorded coupon) + delivery fee
```

The best available offer is the lowest effective total among in-stock sellers.
Live quotes record only the listed price and availability; coupons and delivery
fees are not inferred.

### 7-day estimate

A linear regression is fitted to the latest 30 recorded observations. The app
projects seven days forward and widens a residual-based uncertainty band. The
confidence label uses fit quality (`R²`), residual size, and observation count.
It is an **estimate**, not a guarantee.

### Suggested target

The target suggestion is anchored to the lower quartile, the recorded minimum,
or the lower end of the forecast, rounded to a sensible level and kept below the
current price. A target is a watch level, not a promised future price.

### Known limitations

- Live extraction depends on the retailer's public HTML. JavaScript-only pages,
  layout changes, bot checks, or regional blocks can prevent a quote.
- Only INR quotes are supported. No currency conversion is performed.
- Live history starts at the first successful import or refresh and is **not
  backfilled** from the retailer.
- Demo coupons, delivery fees, and seller offers are synthetic; they do not
  describe a real checkout.
- Forecasts are statistical estimates with uncertainty, not buying advice.
- The app has no user accounts or per-user data isolation. Treat the database as
  single-user for this demo.

---

## Local vs AI feature matrix

| Capability | Without `OPENROUTER_API_KEY` | With a working key |
|---|---|---|
| Dashboard, catalog, product detail | Yes | Yes |
| Live quote import and refresh | Yes | Yes |
| Price history and charts | Yes | Yes |
| Deal score and component breakdown | Yes | Yes |
| Offer comparison | Yes | Yes |
| 7-day regression estimate | Yes | Yes |
| Target-price watchlist | Yes | Yes |
| Copilot answers | Deterministic built-in analysis | Model-written explanation grounded in the same data |
| Copilot watchlist commands | Yes, written directly by Python | Yes, written directly by Python; no AI call |
| Quick prompts | Yes | Yes |
| Missing-data explanations | Yes | Yes |
| External network calls | Retailer pages only, on explicit import/refresh | Retailer pages plus the model provider |
| Failure notice | Clear live quote error; no invented price | Warning + clearly labelled built-in fallback |

---

## Project structure

```text
PyProject/
├── app.py                          # Streamlit entry point and page routing
├── requirements.txt                # Runtime dependencies
├── requirements-dev.txt            # pytest + Playwright
├── .env.example                    # Safe configuration template
├── .gitignore                      # Excludes .env, database, caches
├── .streamlit/config.toml          # Dark theme base configuration
├── data/
│   └── shopping.db                 # Generated SQLite database (gitignored)
├── smartdeal/
│   ├── config.py                   # Settings and server-side secret loading
│   ├── database.py                 # Schema, migrations, CRUD, live persistence
│   ├── seed.py                     # Deterministic 40-product demo catalog
│   ├── analytics.py                # Stats, deal score, forecast, offers, targets
│   ├── live/
│   │   ├── scraper.py              # URL checks, fetching, parsing, adapters
│   │   ├── service.py              # Import, refresh, source management
│   │   ├── seed.py                 # Verified recorded quotes for the demo
│   │   ├── status.py               # Freshness and provenance labels
│   │   └── __init__.py             # Public live-quote API
│   ├── copilot/
│   │   ├── context.py              # Grounded JSON shopping context
│   │   ├── local_answers.py        # Deterministic intent-based answers
│   │   ├── openrouter.py           # Server-side client, retries, sanitised errors
│   │   └── service.py              # Orchestration, system prompt, actions
│   └── ui/
│       ├── theme.py                # Premium CSS and responsive drawer layout
│       ├── components.py           # Cards, charts, badges, live/demo panels
│       ├── views.py                # Ten sections and live quote workspace
│       └── copilot.py              # Floating panel, chat state, composer, JS
└── tests/
    ├── conftest.py                 # Temporary DB and offline settings
    ├── test_analytics.py           # Calculations and forecasts
    ├── test_database.py            # Schema, seeding, watchlist behavior
    ├── test_live.py                # Parsing, SSRF, import/refresh, provenance
    ├── test_copilot.py             # Grounding, fallback, actions, AI failures
    ├── test_openrouter.py          # HTTP status/error handling
    ├── test_config.py              # Secret and configuration handling
    ├── test_ui_smoke.py            # Optional Playwright browser tests
    └── mock_openrouter_failure.py  # Local 429 server for failure-state testing
```

### Key design decisions

- **Streamlit-native drawer** — the panel is a keyed Streamlit container with
  fixed positioning, not a separate frontend. It preserves session state and
  avoids a second server process.
- **Python owns the numbers** — the model explains snapshots produced by
  `analytics.py`; it does not calculate or mutate data.
- **Deterministic built-in fallback** — the same context powers both built-in and
  model-written answers, so the app remains useful without a key and failures
  are transparent.
- **Live and demo stay separate** — a live product is created only by importing a
  product page; demo rows are never presented as live quotes.
- **No scikit-learn** — the forecast uses NumPy linear regression, keeping the
  dependency footprint small.
- **Altair 6.3** — required for compatibility with the Python 3.14 environment.
- **Streamlit 1.66 APIs** — the UI uses `width="stretch"` and `st.iframe`, which
  are available in the pinned minimum version.

---

## Testing

### Offline unit and integration tests

```powershell
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: **94 passed**, with the four Playwright tests skipped unless a browser
URL is configured. The tests use temporary SQLite databases and mocked
network/AI responses; no external network access is required.

Coverage includes:

- Deal-score components, labels, savings, and effective offer totals.
- Forecast availability, direction, uncertainty bounds, and confidence.
- SQLite initialization, migrations, product bundles, watchlist upsert/remove,
  demo seeding, and live/demo separation.
- Persistent alerts: target sync and dedupe, price/stock change detection,
  quote attention and recovery, read/dismiss/clear flows.
- Purchase records: validation, upsert/remove, comparison with the current
  price, and portfolio summaries.
- Shareable deep links: page slugs, product/compare query parsing, and URL
  building.
- Stale-only refresh: fresh products are skipped, stale products refresh, and
  the no-live-products case is handled.
- Live URL validation, SSRF blocking, robots handling, Amazon/Flipkart selectors,
  generic JSON-LD parsing, blocked/priceless pages, stale labels, import, failed
  refresh, multiple sources, INR rejection, source removal, and guarded removal
  of a live product with its history, offers, sources, and watch target.
- All six quick prompts, product questions, missing context, missing history, and
  missing offers.
- Budget filtering, comparisons, target suggestions, and watchlist commands.
- AI success, redaction, failure fallback, history trimming, and “no key means no
  call”.
- Provider 401/402/429/5xx, timeout, network, malformed JSON, retry behavior, and
  sanitised errors.
- Configuration parsing, placeholder keys, timeout clamping, and `.env` handling.

### Optional browser smoke tests

Start the app in one terminal:

```powershell
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\streamlit.exe run app.py --server.port 8501 --server.headless true --server.fileWatcherType none
```

Run the browser tests in another:

```powershell
$env:COPILOT_BASE_URL = "http://localhost:8501"
.\.venv\Scripts\python.exe -m pytest tests/test_ui_smoke.py -q
```

The browser tests cover:

- Opening and closing the panel.
- The exact empty-state heading.
- All six quick prompts.
- A product-specific answer with recorded values.
- Missing-context clarification.
- Chat history surviving close/reopen.
- Mobile viewport fit at 390×844 with a visible composer.
- The loading spinner and failed-AI warning (when a failure URL is supplied).

By default the tests launch Microsoft Edge (`channel="msedge"`). To use bundled
Chromium instead:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
$env:COPILOT_BROWSER_CHANNEL = "chromium"
```

### Simulate a failed AI request

The optional failure test exercises the real UI warning path. Start the mock
429 server:

```powershell
.\.venv\Scripts\python.exe tests\mock_openrouter_failure.py
```

Start a second app instance with a deliberately failing endpoint:

```powershell
$env:OPENROUTER_API_KEY = "sk-test-failure-only"
$env:OPENROUTER_MODEL = "test/failing-model"
$env:OPENROUTER_API_URL = "http://127.0.0.1:8765/api/v1/chat/completions"
$env:AI_COPILOT_TIMEOUT = "10"
.\.venv\Scripts\streamlit.exe run app.py --server.port 8502 --server.headless true --server.fileWatcherType none
```

Run both local and failure UI tests:

```powershell
$env:COPILOT_BASE_URL = "http://localhost:8501"
$env:COPILOT_FAILURE_BASE_URL = "http://localhost:8502"
.\.venv\Scripts\python.exe -m pytest tests/test_ui_smoke.py -q
```

Expected: **4 passed**. The failure test waits for the spinner, then verifies the
rate-limit warning, the **Built-in analysis** badge, and the local answer text. No
model response is fabricated.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Sidebar says **Guided analysis** | Add `OPENROUTER_API_KEY` to `.env` and restart Streamlit. |
| AI request fails | Check the warning text, network access, key validity, credits, and model ID. The built-in answer remains available. |
| Live import says the URL is not a product page | Open one specific item and copy its address-bar URL. Amazon.in URLs contain `/dp/`; Flipkart URLs contain `/p/`. |
| Live import says the page was blocked | The retailer returned a CAPTCHA, login, or access-denied page. The app does not bypass it. Try later or use an official API/feed. |
| Live import says price not found | The page may be JavaScript-only, out of stock, or structurally changed. The app will not guess a price. |
| Live quote is stale | Press **Refresh** on the product or **Refresh all live quotes**. If the retailer still blocks the check, the last good quote is kept and labelled. |
| Live quote is in another currency | Only INR is supported. No conversion is performed. |
| Changes to Python/CSS do not appear | Restart Streamlit. The demo command uses `--server.fileWatcherType none`, which leaves imported modules cached. |
| Database cannot be initialized | Ensure the `data/` directory is writable, or set `SHOPPING_DB_PATH` to a writable path. |
| Want the original demo state | Stop the app, delete `data/shopping.db`, and restart. This also removes imported live products. |
| Browser tests cannot find Edge | Install Edge or set `COPILOT_BROWSER_CHANNEL=chromium` after installing Playwright Chromium. |
| `pytest` cannot import `smartdeal` | Run `python -m pytest` from the project root, not a bare `pytest` executable. |

---

## Security and responsible use

- [x] `.env` and `.streamlit/secrets.toml` are gitignored.
- [x] The model API key is read only in the Python process.
- [x] The key is never placed in prompts or browser HTML.
- [x] Model output and error details are sanitised; the key is redacted.
- [x] The browser never calls the model provider directly.
- [x] Watchlist writes happen only in Python, with explicit action parsing.
- [x] The model is instructed not to reveal system prompts or configuration.
- [x] Live URLs are validated to block local/private network targets.
- [x] Live fetching respects `robots.txt` and rate-limits per host.
- [x] CAPTCHAs, logins, paywalls, and anti-bot controls are never bypassed.
- [x] Live and demo data are labelled separately; no invented prices or details.
- [x] Only INR quotes are accepted; unsupported currencies are rejected.

For a public deployment, also use HTTPS, a platform secret manager, restricted
network egress if required, and appropriate access controls. This demo does not
include user accounts or per-user data isolation.

**Retailer terms:** automated access to marketplace pages may be restricted by
the retailer's terms of service. Use official APIs, affiliate feeds, or explicit
permission for production use. The live importer is intended for personal,
low-volume demonstration and respects access controls rather than evading them.

---

## License / provenance

This is a self-contained demo project. The 40-product demo catalog, its price
observations, seller names, coupons, and watchlist entries are synthetic and
generated locally for demonstration. They are not live marketplace data and
should not be used for real purchasing decisions.

Live quotes, when imported, are the last successful reading of a public product
page and can become stale or unavailable. Always confirm price, seller, coupons,
delivery, and availability on the retailer's own checkout page before buying.
