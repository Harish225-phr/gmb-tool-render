import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
from typing import List, Optional, Tuple
from providers.base import BaseSearchProvider, LeadData, ProviderError
from services.domain_service import DomainService
import logging

logger = logging.getLogger(__name__)

class PublicDirectoryProvider(BaseSearchProvider):
    """
    Public Business Directory Provider (YellowPages Public Listings).
    Extracts business listings, official website links, ratings, and review counts.
    Honors rate limits, validates responses, and reports blocks honestly.
    """

    DIRECTORY_URL = "https://www.yellowpages.com/search"

    def __init__(self, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", timeout: int = 12):
        super().__init__(name="YellowPages Directory")
        self.user_agent = user_agent
        self.timeout = timeout

    @staticmethod
    def _parse_rating_class(classes: List[str]) -> Optional[float]:
        """Parses classes like 'result-rating four half' or 'rating-4_5' into float."""
        for c in classes:
            c_lower = c.lower()
            if "one" in c_lower and "half" in c_lower:
                return 1.5
            elif "two" in c_lower and "half" in c_lower:
                return 2.5
            elif "three" in c_lower and "half" in c_lower:
                return 3.5
            elif "four" in c_lower and "half" in c_lower:
                return 4.5
            elif "five" in c_lower:
                return 5.0
            elif "four" in c_lower:
                return 4.0
            elif "three" in c_lower:
                return 3.0
            elif "two" in c_lower:
                return 2.0
            elif "one" in c_lower:
                return 1.0
            
            # Numeric match like rating-4_5
            num_m = re.search(r'rating[_-]?([1-5](?:[._][0-9])?)', c_lower)
            if num_m:
                val = num_m.group(1).replace("_", ".")
                try:
                    return float(val)
                except ValueError:
                    pass
        return None

    def search(self, niche: str, location: str, limit: int = 20) -> List[LeadData]:
        params = {
            "search_terms": niche,
            "geo_location_terms": location
        }
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        search_url = f"{self.DIRECTORY_URL}?{urllib.parse.urlencode(params)}"
        results: List[LeadData] = []

        try:
            resp = requests.get(
                self.DIRECTORY_URL,
                params=params,
                headers=headers,
                timeout=self.timeout
            )

            if resp.status_code in (403, 429):
                raise ProviderError(
                    f"YellowPages Directory returned HTTP {resp.status_code} (access restricted)",
                    provider_name=self.name,
                    is_blocked=True
                )

            if "captcha" in resp.text.lower() or "challenge" in resp.text.lower() and resp.status_code != 200:
                raise ProviderError(
                    "YellowPages challenge detected; skipping provider.",
                    provider_name=self.name,
                    is_blocked=True
                )

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select(".result, .info, .organic .v-card")

            for card in cards:
                # Business name
                name_elem = card.select_one(".business-name, .n a, a.business-name")
                if not name_elem:
                    continue
                biz_name = name_elem.get_text(strip=True)
                if not biz_name:
                    continue

                # Website
                website_elem = card.select_one("a.track-visit-website, a[href*='track-visit-website'], a.website-link")
                raw_website = website_elem.get("href") if website_elem else None
                norm_url, domain, is_valid_site = DomainService.classify_and_resolve_url(raw_website)

                # Rating
                rating = None
                rating_elem = card.select_one(".result-rating, .rating, div[class*='rating']")
                if rating_elem:
                    classes = rating_elem.get("class", [])
                    rating = self._parse_rating_class(classes)

                # Review count
                review_count = None
                count_elem = card.select_one(".count, .ratings-count, span[class*='count']")
                if count_elem:
                    count_text = count_elem.get_text(strip=True)
                    m = re.search(r'([0-9]+)', count_text)
                    if m:
                        try:
                            review_count = int(m.group(1))
                        except ValueError:
                            pass

                # Phone
                phone_elem = card.select_one(".phones, .phone")
                phone = phone_elem.get_text(strip=True) if phone_elem else None

                # Address
                addr_elem = card.select_one(".adr, .street-address, .locality")
                address = addr_elem.get_text(" ", strip=True) if addr_elem else location

                lead = LeadData(
                    business_name=biz_name,
                    category_or_niche=niche,
                    location=location,
                    rating=rating,
                    review_count=review_count,
                    website_url=norm_url if is_valid_site else None,
                    website_domain=domain if is_valid_site else None,
                    source_name=self.name,
                    source_url=search_url,
                    collection_status="live",
                    phone=phone,
                    address=address
                )
                results.append(lead)
                if len(results) >= limit:
                    break

        except ProviderError:
            raise
        except requests.Timeout:
            self.logger.warning("Directory provider timeout for %s %s", niche, location)
        except Exception as e:
            self.logger.error("Error executing Directory provider search: %s", e)

        return results
