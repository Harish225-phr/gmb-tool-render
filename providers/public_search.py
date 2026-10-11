import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
from typing import List, Optional, Tuple
from providers.base import BaseSearchProvider, LeadData, ProviderError
from services.domain_service import DomainService
import logging

logger = logging.getLogger(__name__)

class PublicSearchProvider(BaseSearchProvider):
    """
    Public Web Search Provider (DuckDuckGo HTML / Lite).
    No API key required.
    Parses live search listings, extracts business websites, resolves redirects,
    and extracts ratings/review counts if explicitly present in snippets.
    """

    SEARCH_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", timeout: int = 12):
        super().__init__(name="DuckDuckGo HTML Search")
        self.user_agent = user_agent
        self.timeout = timeout

    @staticmethod
    def _extract_target_url(raw_href: str) -> Optional[str]:
        """Extracts destination URL from DuckDuckGo redirect link /l/?uddg=..."""
        if not raw_href:
            return None
        
        # Check for //duckduckgo.com/l/?uddg=
        if "uddg=" in raw_href:
            try:
                parsed = urllib.parse.urlsplit(raw_href)
                query_dict = urllib.parse.parse_qs(parsed.query)
                if "uddg" in query_dict and query_dict["uddg"]:
                    return urllib.parse.unquote(query_dict["uddg"][0])
            except Exception:
                pass
        
        if raw_href.startswith("//"):
            return "https:" + raw_href
        if raw_href.startswith("http"):
            return raw_href
        return None

    @staticmethod
    def _extract_ratings_from_text(text: str) -> Tuple[Optional[float], Optional[int]]:
        """
        Extracts explicit rating and review count from snippet text if present.
        E.g.: 'Rating: 4.8 · 124 reviews' or '4.9 stars - 52 reviews'
        """
        if not text:
            return None, None
        
        rating = None
        review_count = None

        # Pattern for rating e.g., 4.7 / 5 or 4.8 stars or Rating: 4.8
        rating_match = re.search(r'(?:Rating:\s*|rated\s*)?([1-5]\.[0-9]|[1-5])\s*(?:/\s*5|\s*(?:stars|★|out of 5))', text, re.IGNORECASE)
        if rating_match:
            try:
                val = float(rating_match.group(1))
                if 1.0 <= val <= 5.0:
                    rating = val
            except (ValueError, TypeError):
                pass

        # Pattern for reviews e.g., 125 reviews or (84 reviews)
        reviews_match = re.search(r'([0-9]{1,3}(?:,[0-9]{3})*|\b[0-9]+\b)\s+(?:user\s+)?reviews', text, re.IGNORECASE)
        if reviews_match:
            try:
                cleaned_num = reviews_match.group(1).replace(",", "")
                review_count = int(cleaned_num)
            except (ValueError, TypeError):
                pass

        return rating, review_count

    @staticmethod
    def _clean_business_name(title: str, location: str) -> str:
        """Cleans search title to isolate business name."""
        if not title:
            return "Unknown Business"
        
        # Remove common title suffixes e.g., " | Indianapolis, IN", " - Yelp", " - Official Website"
        name = title
        delimiters = [" | ", " - ", " : ", " – ", " — "]
        for d in delimiters:
            if d in name:
                parts = name.split(d)
                # Take first part if it looks like a business name
                if len(parts[0].strip()) >= 3:
                    name = parts[0]
                    break
        
        # Remove trailing location mentions if present
        name = re.sub(re.escape(location), "", name, flags=re.IGNORECASE).strip()
        name = re.sub(r'[\s\-_]+$', '', name)
        return name.strip() or title.strip()

    def search(self, niche: str, location: str, limit: int = 20) -> List[LeadData]:
        query = f"{niche} {location}"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://html.duckduckgo.com/",
            "Origin": "https://html.duckduckgo.com",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        search_url = f"{self.SEARCH_URL}?q={urllib.parse.quote(query)}"
        results: List[LeadData] = []

        try:
            resp = requests.post(
                self.SEARCH_URL,
                data={"q": query, "b": ""},
                headers=headers,
                timeout=self.timeout
            )
            
            if resp.status_code in (403, 429):
                raise ProviderError(
                    f"DuckDuckGo returned HTTP {resp.status_code} (Rate limited or access denied)",
                    provider_name=self.name,
                    is_blocked=True
                )
            
            if "anomaly" in resp.text.lower() or "bot" in resp.text.lower() and resp.status_code != 200:
                raise ProviderError(
                    "Search provider detected automated query challenge.",
                    provider_name=self.name,
                    is_blocked=True
                )

            soup = BeautifulSoup(resp.text, "lxml")
            result_elements = soup.select(".result, .web-result")
            if not result_elements:
                result_elements = soup.select(".results_links_deep, .result__body")

            for el in result_elements:
                title_elem = el.select_one(".result__a, .result__title a, a.result__url, .result__title")
                if not title_elem:
                    continue
                raw_title = title_elem.get_text(strip=True)
                
                # Find anchor tag for href
                a_elem = title_elem if title_elem.name == "a" else title_elem.find("a")
                if not a_elem:
                    a_elem = el.select_one("a.result__url, a.result__a, a")
                raw_href = a_elem.get("href") if a_elem else None

                snippet_elem = el.select_one(".result__snippet")
                snippet_text = snippet_elem.get_text(" ", strip=True) if snippet_elem else ""

                dest_url = self._extract_target_url(raw_href)
                norm_url, domain, is_valid_website = DomainService.classify_and_resolve_url(dest_url)
                
                # Check for explicit ratings in snippet
                rating, reviews = self._extract_ratings_from_text(snippet_text)

                biz_name = self._clean_business_name(raw_title, location)

                # Even if website is a directory, record lead but identify if official business website
                lead = LeadData(
                    business_name=biz_name,
                    category_or_niche=niche,
                    location=location,
                    rating=rating,
                    review_count=reviews,
                    website_url=norm_url if is_valid_website else None,
                    website_domain=domain if is_valid_website else None,
                    source_name=self.name,
                    source_url=search_url,
                    collection_status="live"
                )
                results.append(lead)
                if len(results) >= limit:
                    break

        except ProviderError:
            raise
        except requests.Timeout:
            self.logger.warning("Search provider timeout for query '%s'", query)
        except Exception as e:
            self.logger.error("Error executing DuckDuckGo search: %s", e)

        return results
