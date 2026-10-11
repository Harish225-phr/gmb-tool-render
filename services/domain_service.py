import re
import urllib.parse
from typing import Optional, Tuple
import logging

try:
    import tldextract
    _TLD_EXTRACTOR = tldextract.TLDExtract()
except ImportError:
    _TLD_EXTRACTOR = None

logger = logging.getLogger(__name__)

# Common tracking / noise query parameters
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "dclid", "ref", "referrer", "source",
    "campaign", "_ga", "_gl", "mc_cid", "mc_eid"
}

# Domains that represent directories, aggregators, or social media rather than a business's direct website
EXCLUDED_OR_DIRECTORY_DOMAINS = {
    "google.com", "maps.google.com", "bing.com", "duckduckgo.com", "yahoo.com",
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "youtube.com", "tiktok.com", "pinterest.com",
    "yelp.com", "yellowpages.com", "yp.com", "angi.com", "angieslist.com",
    "homeadvisor.com", "thumbtack.com", "bbb.org", "manta.com", "mapquest.com",
    "tripadvisor.com", "foursquare.com", "nextdoor.com", "superpages.com",
    "chamberofcommerce.com", "citysearch.com", "groupon.com", "houzz.com",
    "wikidata.org", "wikipedia.org", "openstreetmap.org"
}

class DomainService:
    """Service for extracting, normalizing, and classifying website URLs and registrable domains."""

    @classmethod
    def clean_and_normalize_url(cls, raw_url: Optional[str]) -> Optional[str]:
        """
        Takes a raw URL (which might lack scheme, contain trailing fragments or tracking query params)
        and returns a normalized canonical URL string.
        """
        if not raw_url:
            return None
        
        raw_url = str(raw_url).strip()
        if not raw_url or raw_url.lower().startswith("mailto:") or "@" in raw_url.split("/")[0]:
            return None
        
        # If no scheme, add https://
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw_url):
            raw_url = "https://" + raw_url
        
        try:
            parsed = urllib.parse.urlsplit(raw_url)
        except Exception:
            return None

        # Scheme must be http or https
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return None

        netloc = parsed.netloc.strip().lower()
        if not netloc:
            return None

        # Handle IDN (Internationalized Domain Names)
        try:
            # Check if netloc contains port
            if ":" in netloc:
                host, port = netloc.split(":", 1)
                host = host.encode("idna").decode("ascii")
                netloc = f"{host}:{port}"
            else:
                netloc = netloc.encode("idna").decode("ascii")
        except Exception:
            pass  # keep netloc as is if idna conversion fails

        # Clean query parameters (strip tracking)
        query = parsed.query
        if query:
            q_pairs = urllib.parse.parse_qsl(query, keep_blank_values=False)
            filtered_pairs = [(k, v) for k, v in q_pairs if k.lower() not in TRACKING_PARAMS]
            clean_query = urllib.parse.urlencode(filtered_pairs)
        else:
            clean_query = ""

        # Normalize path: remove redundant trailing slash if root
        path = parsed.path
        if not path or path == "/":
            path = ""
        else:
            # normalize double slashes
            path = re.sub(r"/+", "/", path)

        # Build normalized URL (drop fragments)
        clean_url = urllib.parse.urlunsplit((scheme, netloc, path, clean_query, ""))
        return clean_url

    @classmethod
    def extract_registrable_domain(cls, url: Optional[str]) -> Optional[str]:
        """
        Extract the registrable domain (e.g. 'example.com' or 'example.co.uk')
        handling public suffixes and internationalized domains.
        """
        if not url:
            return None

        norm_url = cls.clean_and_normalize_url(url)
        if not norm_url:
            return None

        try:
            parsed = urllib.parse.urlsplit(norm_url)
            hostname = parsed.netloc.split(":")[0].lower()
            if not hostname:
                return None
            
            # Remove leading 'www.'
            if hostname.startswith("www."):
                hostname = hostname[4:]

            if _TLD_EXTRACTOR:
                ext = _TLD_EXTRACTOR(hostname)
                if ext.domain and ext.suffix:
                    return f"{ext.domain}.{ext.suffix}".lower()
            
            # Fallback simple PSL logic
            parts = hostname.split(".")
            if len(parts) >= 2:
                # Common two-level suffixes
                two_level_tlds = {"co.uk", "org.uk", "gov.uk", "ac.uk", "com.au", "net.au", "org.au", "co.nz", "co.in", "net.in", "co.za"}
                if len(parts) >= 3 and f"{parts[-2]}.{parts[-1]}" in two_level_tlds:
                    return ".".join(parts[-3:])
                return ".".join(parts[-2:])
            return hostname
        except Exception as e:
            logger.debug("Failed extracting domain from %s: %s", url, e)
            return None

    @classmethod
    def is_social_or_directory(cls, url_or_domain: Optional[str]) -> bool:
        """Checks if a URL or domain belongs to social media or major public directory/aggregator."""
        if not url_or_domain:
            return False
        domain = cls.extract_registrable_domain(url_or_domain)
        if not domain:
            return False
        return domain.lower() in EXCLUDED_OR_DIRECTORY_DOMAINS

    @classmethod
    def classify_and_resolve_url(cls, raw_url: Optional[str]) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Processes a raw URL and returns:
        (normalized_url, registrable_domain, is_valid_business_website)
        """
        if not raw_url:
            return None, None, False
        
        normalized = cls.clean_and_normalize_url(raw_url)
        if not normalized:
            return None, None, False
        
        domain = cls.extract_registrable_domain(normalized)
        if not domain:
            return None, None, False
        
        is_directory = cls.is_social_or_directory(domain)
        is_valid = not is_directory

        return normalized, domain, is_valid
