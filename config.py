import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "lead-scraper-secret-render-key-2026")
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG = os.environ.get("FLASK_ENV") == "development"

    # Scraping & HTTP settings
    REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 12))  # seconds
    MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 2))
    USER_AGENT = os.environ.get(
        "SCRAPER_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 LeadResearchBot/1.0"
    )

    # Worker pool & rate limits
    MAX_WORKERS = int(os.environ.get("MAX_WORKERS", 2))
    DELAY_BETWEEN_REQUESTS = float(os.environ.get("DELAY_BETWEEN_REQUESTS", 1.0))
    DEFAULT_LIMIT_PER_LOCATION = 20
    MAX_LOCATIONS_PER_SEARCH = 25
    MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB max per page

    # Job Manager
    JOB_RETENTION_SECONDS = 3600  # 1 hour
    MAX_ACTIVE_JOBS = 50

    # Enabled providers
    ENABLED_PROVIDERS = [
        "osm_overpass",
        "public_search",
        "public_directory"
    ]
