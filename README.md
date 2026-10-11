# LeadPulse — Production-Ready No-API-Key Local Business Lead Scraper

LeadPulse is a full-stack local business lead scraper and web dashboard designed specifically to discover potential B2B web design and marketing clients across multiple cities without requiring any paid API keys (such as Google Places API or SerpApi). It is engineered for lightweight, zero-cost deployment on the **Render Free Tier Web Service**.

---

## Key Features

1. **Multi-Location Search Pipeline**
   - Query 5–10+ cities in a single submission (e.g., Indianapolis, Carmel, Fishers, Noblesville, Greenwood, Avon).
   - Automatic trimming of whitespace and case-insensitive deduplication of target locations.
   - Paced, rate-limited execution to operate comfortably within free server CPU and memory constraints.

2. **No-API-Key Provider Architecture**
   - **OpenStreetMap (Overpass API & Nominatim):** 100% public, open data. Extracts verified local business names, addresses, phone numbers, and official websites.
   - **DuckDuckGo HTML/Lite Search:** Public search parsing that extracts candidate business websites, unwraps search engine redirects, and pulls explicit ratings/reviews when present in search snippets.
   - **Public Directory Scraper (YellowPages):** Fallback provider for commercial directory listings with defensive HTML parsing.
   - **Honest Data Provenance:** Ratings and reviews are stored only when explicitly verified by the source. Missing data is stored as `null` / `None` and never fabricated.

3. **Domain Normalization & Classification**
   - Powered by a Public Suffix List (PSL) engine (`tldextract`) to isolate registrable domains (e.g., `example.co.uk`, `contractor.com`).
   - Strips tracking query parameters (`utm_*`, `fbclid`, `gclid`, etc.) and anchor fragments.
   - Automatically filters out social media links (Facebook, Instagram, LinkedIn) and aggregator platforms (Yelp, YellowPages, BBB, Angi) so only genuine business websites are cataloged.
   - Flags businesses that have **no website**, highlighting prime candidates for agency outreach.

4. **Multi-Tier Deduplication & Honest Statistics**
   - **1st-Tier (Domain Level):** Consolidates businesses sharing the same registrable domain.
   - **2nd-Tier (Name + Location Level):** Normalizes business titles (stripping legal suffixes like LLC, Inc., Corp., Co.) and combines with location.
   - **Cross-Location Grouping:** Preserves branch distinctions across separate cities unless identical domains prove common ownership.
   - **Honest Summary Statistics:** Computes average ratings *only* over leads with confirmed numerical ratings. Missing ratings are never counted as 0.

5. **Bulk Clipboard & Export Utilities**
   - **Copy Selected Websites:** Copies unique URLs of selected rows (one per line).
   - **Copy All Websites:** Copies every unique business website discovered.
   - **Copy Unique Domains:** Copies clean registrable domains.
   - **Copy Selected Leads (TSV):** Tab-separated format ready for direct pasting into Microsoft Excel or Google Sheets.
   - **Copy Without Websites:** Copies business names and locations lacking a website.
   - **CSV Export:** Generates UTF-8 with BOM files with formula injection protection (neutralizing `=`, `+`, `-`, `@`, `\t` prefixes) and timestamped filenames.

6. **Application Security & SSRF Defense**
   - Blocks private IP ranges (RFC 1918: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopbacks (`127.0.0.1`, `::1`), and cloud metadata IP endpoints (`169.254.169.254`, `metadata.google.internal`).
   - Re-validates every redirect hop before following.
   - Strict limits on input sizes, concurrent workers, and response byte caps (5MB max).

---

## Project Structure

```
├── app.py                      # Flask web application & REST endpoints
├── config.py                   # Central configuration & environment variables
├── requirements.txt            # Python dependencies (Render compatible)
├── render.yaml                 # Render Infrastructure-as-Code Blueprint
├── README.md                   # Documentation & deployment guide
├── .gitignore                  # Git ignore rules
├── providers/
│   ├── __init__.py
│   ├── base.py                 # LeadData model & BaseSearchProvider interface
│   ├── osm_overpass.py         # OpenStreetMap Overpass & Nominatim provider
│   ├── public_search.py        # DuckDuckGo HTML search provider
│   └── public_directory.py     # Public business directory fallback provider
├── services/
│   ├── __init__.py
│   ├── domain_service.py       # PSL domain extraction, URL normalization, classification
│   ├── deduplication_service.py# Multi-level deduping & honest stats calculation
│   ├── security_service.py     # SSRF defense, IP filtering, spreadsheet sanitization
│   ├── export_service.py       # CSV (UTF-8 BOM) and TSV generation
│   └── search_service.py       # Asynchronous in-memory job manager & provider fallback
├── templates/
│   └── index.html              # Responsive Bootstrap 5 dashboard
├── static/
│   ├── css/
│   │   └── style.css           # Modern design tokens, cards, and animations
│   └── js/
│       └── app.js              # Real-time job polling, filtering, clipboard & exports
└── tests/
    ├── __init__.py
    ├── test_domains.py         # Domain normalization and extraction tests
    ├── test_deduplication.py   # Deduplication & honest rating tests
    ├── test_exports.py         # CSV BOM, escaping, and formula injection tests
    ├── test_security.py        # SSRF IP blocking and input validation tests
    └── test_search.py          # Provider orchestration and partial failure tests
```

---

## Local Installation & Quickstart

### Prerequisites
- Python 3.11, 3.12, 3.13, or 3.14
- Git

### 1. Clone & Set Up Virtual Environment

```bash
git clone <your-repository-url>
cd lead-scraper

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Automated Tests

Run the full pytest test suite (25 automated tests):

```bash
pytest -v
```

All tests run locally using mocked HTML fixtures and defensive security checks, requiring zero external API keys or live network dependencies.

### 4. Start the Development Server

```bash
python app.py
```

Open your browser to: **`http://localhost:5000`**

To test under production Gunicorn locally (on Linux/macOS or WSL):
```bash
gunicorn app:app --workers 2 --threads 2 --bind 0.0.0.0:5000
```

---

## Search Provider Capabilities & Limitations

| Provider | Requires API Key? | Business Name | Website URL | Phone / Address | Rating & Review Count | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **OpenStreetMap (Overpass)** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes | ❌ None (`null`) | OSM does not host user reviews. Data is 100% verified and licensed under ODbL. |
| **DuckDuckGo HTML Search** | ❌ No | ✅ Yes | ✅ Yes | ⚠️ Snippet only | ⚠️ Snippet text regex | Extracts actual ratings/reviews when present in search snippets. |
| **YellowPages Directory** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes | ✅ When listed | Public directory listing. Subject to anti-bot challenges if queried too quickly. |

### Real-World Limitations of the No-API-Key Approach
1. **Missing Ratings:** Free public map databases (OpenStreetMap) do not record proprietary consumer reviews (like Google Reviews or Yelp Stars). These fields are honestly returned as `null` rather than generating artificial data.
2. **Provider Rate Limiting (HTTP 429/403):** Public search engines can challenge automated traffic if requests are too frequent. The application mitigates this using:
   - Sequential, paced batching with configurable delays (`DELAY_BETWEEN_REQUESTS = 1.0s`).
   - Provider fallback: If DuckDuckGo issues a challenge, the search engine catches `ProviderError(is_blocked=True)` and seamlessly shifts to OpenStreetMap and Directory providers without stopping the job or dropping prior leads.
3. **Ephemeral Storage:** The background job manager is in-memory. Because Render's free tier spins down inactive instances after 15 minutes of inactivity, historical jobs disappear upon sleep or restart. You should export results to CSV upon completion.

---

## Deploying to Render Free Web Service

### Option A: Using `render.yaml` (Recommended)

1. Push this codebase to a GitHub or GitLab repository.
2. Log in to [Render](https://dashboard.render.com).
3. Click **New +** > **Blueprint**.
4. Select your connected repository.
5. Render will automatically detect `render.yaml` and configure:
   - **Environment:** `Python 3.11`
   - **Plan:** `Free`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --workers 2 --threads 2 --bind 0.0.0.0:$PORT --timeout 120`
6. Click **Apply**.

### Option B: Manual Web Service Setup

1. In Render Dashboard, click **New +** > **Web Service**.
2. Connect your repository.
3. Configure the following fields:
   - **Name:** `lead-scraper`
   - **Runtime:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --workers 2 --threads 2 --bind 0.0.0.0:$PORT --timeout 120`
   - **Instance Type:** `Free`
4. Add Environment Variables (Optional):
   - `PORT`: Automatically set by Render.
   - `MAX_WORKERS`: `2`
   - `DELAY_BETWEEN_REQUESTS`: `1.0`
   - `REQUEST_TIMEOUT`: `12`
5. Click **Create Web Service**.

### Understanding Render Free Tier Lifecycle
- **Cold Starts:** Free tier Web Services spin down (sleep) after 15 minutes of no HTTP requests. When a new visitor opens the URL, a cold start takes ~30–50 seconds to boot the container.
- **Port Binding:** The Flask app reads `PORT` from environment variables and binds to `0.0.0.0:$PORT`.
- **Memory Cap:** Render free tier provides 512 MB RAM. The scraper uses gentle concurrency (2 threads), streaming responses, and response size limits (5 MB max) to prevent Out-Of-Memory (OOM) termination.

---

## Troubleshooting Guide

- **HTTP 403 / 429 Warnings:**
  - If a public provider temporarily rate limits requests, look at the **Progress Bar warnings banner**. The scraper marks the provider as blocked for that location and continues with remaining providers.
  - Increase `DELAY_BETWEEN_REQUESTS` in `config.py` to `2.0` or `3.0` seconds if querying large batches.
- **Timeout on a Location:**
  - Render free tier has a 100-second web request timeout. Searches in LeadPulse run in a background daemon thread with client-side polling (`/api/jobs/<id>`), ensuring web request timeouts never occur.
- **Missing Website URLs:**
  - Many local tradespeople (plumbers, roofers, mechanics) operate solely via word-of-mouth or phone numbers without an official domain. Use the **Copy Without Websites** or **Export Businesses Without Websites** button to target them for web development sales outreach!
