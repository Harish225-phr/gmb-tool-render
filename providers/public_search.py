import requests
from bs4 import BeautifulSoup
import urllib.parse
import base64
import re
from typing import List, Optional, Tuple
from providers.base import BaseSearchProvider, LeadData, ProviderError
from services.domain_service import DomainService
import logging

logger = logging.getLogger(__name__)

class PublicSearchProvider(BaseSearchProvider):
    """
    Public Web Search Provider (Bing + DuckDuckGo Fallback).
    No API key required.
    Parses live search listings, extracts business websites, resolves redirects,
    and extracts ratings/review counts and phone numbers if present in snippets.
    """

    BING_URL = "https://www.bing.com/search"
    DDG_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36", timeout: int = 12):
        super().__init__(name="Public Web Search")
        self.user_agent = user_agent
        self.timeout = timeout

    @staticmethod
    def _decode_bing_url(href: str) -> Optional[str]:
        """Decodes Bing redirect URL containing base64 destination in &u=..."""
        if not href:
            return None
        if "bing.com/ck/a" in href:
            m = re.search(r'[?&]u=([a-zA-Z0-9_\-]+)', href)
            if m:
                val = m.group(1)
                if len(val) > 2 and val[:2] in ('a1', 'a0'):
                    val = val[2:]
                val = val.replace('-', '+').replace('_', '/')
                val += '=' * ((4 - len(val) % 4) % 4)
                try:
                    decoded = base64.b64decode(val).decode('utf-8', errors='ignore')
                    if decoded.startswith('http'):
                        return decoded
                except Exception:
                    pass
        elif href.startswith('http') and 'bing.com' not in href:
            return href
        return None

    @staticmethod
    def _extract_ddg_target_url(raw_href: str) -> Optional[str]:
        """Extracts destination URL from DuckDuckGo redirect link /l/?uddg=..."""
        if not raw_href:
            return None
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
        """Extracts explicit rating and review count from snippet text if present."""
        if not text:
            return None, None
        
        rating = None
        review_count = None

        rating_match = re.search(r'(?:Rating:\s*|rated\s*)?([1-5]\.[0-9]|[1-5])\s*(?:/\s*5|\s*(?:stars|★|out of 5))', text, re.IGNORECASE)
        if rating_match:
            try:
                val = float(rating_match.group(1))
                if 1.0 <= val <= 5.0:
                    rating = val
            except (ValueError, TypeError):
                pass

        reviews_match = re.search(r'([0-9]{1,3}(?:,[0-9]{3})*|\b[0-9]+\b)\s+(?:user\s+)?reviews', text, re.IGNORECASE)
        if reviews_match:
            try:
                cleaned_num = reviews_match.group(1).replace(",", "")
                review_count = int(cleaned_num)
            except (ValueError, TypeError):
                pass

        return rating, review_count

    @staticmethod
    def _extract_phone(text: str) -> Optional[str]:
        """Extracts US / standard formatted phone number from snippet text."""
        if not text:
            return None
        m = re.search(r'(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}', text)
        return m.group(0) if m else None

    @staticmethod
    def _clean_business_name(title: str, location: str) -> str:
        """Cleans search title to isolate genuine business name."""
        if not title:
            return "Local Business"
        name = title
        delimiters = [" | ", " - ", " : ", " – ", " — "]
        for d in delimiters:
            if d in name:
                parts = name.split(d)
                if len(parts[0].strip()) >= 3:
                    name = parts[0]
                    break
        name = re.sub(re.escape(location), "", name, flags=re.IGNORECASE).strip()
        name = re.sub(r'[\s\-_]+$', '', name)
        return name.strip() or title.strip()

    def _search_bing(self, niche: str, location: str, limit: int = 20) -> List[LeadData]:
        """Queries Bing public web search."""
        query = f'"{niche}" {location}'
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
        url = f"{self.BING_URL}?q={urllib.parse.quote(query)}&count=25"
        leads: List[LeadData] = []

        try:
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select("li.b_algo")
                for card in cards:
                    a_elem = card.select_one("h2 a")
                    if not a_elem:
                        continue
                    raw_title = a_elem.get_text(strip=True)
                    raw_href = a_elem.get("href", "")
                    dest_url = self._decode_bing_url(raw_href)
                    if not dest_url:
                        continue

                    snippet_elem = card.select_one(".b_caption p, .b_snippet, .b_lineclamp2")
                    snippet_text = snippet_elem.get_text(" ", strip=True) if snippet_elem else ""

                    norm_url, domain, is_valid_website = DomainService.classify_and_resolve_url(dest_url)
                    rating, reviews = self._extract_ratings_from_text(snippet_text)
                    phone = self._extract_phone(snippet_text)
                    biz_name = self._clean_business_name(raw_title, location)

                    lead = LeadData(
                        business_name=biz_name,
                        category_or_niche=niche,
                        location=location,
                        rating=rating,
                        review_count=reviews,
                        website_url=norm_url if is_valid_website else None,
                        website_domain=domain if is_valid_website else None,
                        source_name="Public Web Search (Bing)",
                        source_url=dest_url,
                        collection_status="live",
                        phone=phone
                    )
                    leads.append(lead)
                    if len(leads) >= limit:
                        break
        except Exception as e:
            self.logger.warning("Bing search notice for %s %s: %s", niche, location, e)

        return leads

    def _search_ddg(self, niche: str, location: str, limit: int = 20) -> List[LeadData]:
        """Queries DuckDuckGo HTML search fallback."""
        query = f"{niche} {location}"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://html.duckduckgo.com/",
            "Origin": "https://html.duckduckgo.com",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        leads: List[LeadData] = []
        try:
            resp = requests.post(
                self.DDG_URL,
                data={"q": query, "b": ""},
                headers=headers,
                timeout=self.timeout
            )
            if resp.status_code == 200 and "anomaly" not in resp.text.lower():
                soup = BeautifulSoup(resp.text, "lxml")
                result_elements = soup.select(".result, .web-result, .results_links_deep")
                for el in result_elements:
                    title_elem = el.select_one(".result__a, .result__title a, a.result__url")
                    if not title_elem:
                        continue
                    raw_title = title_elem.get_text(strip=True)
                    a_elem = title_elem if title_elem.name == "a" else title_elem.find("a")
                    raw_href = a_elem.get("href") if a_elem else None
                    dest_url = self._extract_ddg_target_url(raw_href)

                    snippet_elem = el.select_one(".result__snippet")
                    snippet_text = snippet_elem.get_text(" ", strip=True) if snippet_elem else ""

                    norm_url, domain, is_valid_website = DomainService.classify_and_resolve_url(dest_url)
                    rating, reviews = self._extract_ratings_from_text(snippet_text)
                    phone = self._extract_phone(snippet_text)
                    biz_name = self._clean_business_name(raw_title, location)

                    lead = LeadData(
                        business_name=biz_name,
                        category_or_niche=niche,
                        location=location,
                        rating=rating,
                        review_count=reviews,
                        website_url=norm_url if is_valid_website else None,
                        website_domain=domain if is_valid_website else None,
                        source_name="DuckDuckGo Search",
                        source_url=dest_url or f"{self.DDG_URL}?q={urllib.parse.quote(query)}",
                        collection_status="live",
                        phone=phone
                    )
                    leads.append(lead)
                    if len(leads) >= limit:
                        break
        except Exception as e:
            self.logger.warning("DuckDuckGo search notice: %s", e)

        return leads

    def search(self, niche: str, location: str, limit: int = 20) -> List[LeadData]:
        # Try Bing first for high-reliability results
        results = self._search_bing(niche, location, limit=limit)
        
        # If Bing returned fewer than requested, supplement with DuckDuckGo
        if len(results) < limit:
            remaining = limit - len(results)
            ddg_results = self._search_ddg(niche, location, limit=remaining)
            if ddg_results:
                results.extend(ddg_results)

        return results
