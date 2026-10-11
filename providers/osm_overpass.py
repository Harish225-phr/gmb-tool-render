import requests
import urllib.parse
from typing import List, Optional
import time
from providers.base import BaseSearchProvider, LeadData, ProviderError
from services.domain_service import DomainService
import logging

logger = logging.getLogger(__name__)

# Comprehensive tag mappings for business niches
NICHE_TAG_MAP = {
    "plumber": ["craft=plumber", "shop=plumber", "craft=drainage"],
    "electrician": ["craft=electrician", "shop=electrical"],
    "hvac": ["craft=hvac", "craft=air_conditioning", "craft=heating_installation", "shop=hvac", "office=hvac"],
    "roofer": ["craft=roofer", "craft=roofing"],
    "restaurant": ["amenity=restaurant", "amenity=fast_food", "amenity=cafe"],
    "cafe": ["amenity=cafe", "shop=coffee"],
    "salon": ["shop=hairdresser", "shop=beauty", "shop=massage", "amenity=spa"],
    "hotel": ["tourism=hotel", "tourism=motel", "tourism=guest_house"],
    "dentist": ["amenity=dentist", "healthcare=dentist"],
    "lawyer": ["office=lawyer", "office=legal"],
    "bakery": ["shop=bakery"],
    "auto repair": ["shop=car_repair", "craft=car_repair", "shop=tyres"],
    "mechanic": ["shop=car_repair", "craft=car_repair"],
    "bar": ["amenity=bar", "amenity=pub"],
    "gym": ["leisure=fitness_centre"],
    "cleaning": ["craft=cleaner", "shop=dry_cleaning"],
    "accountant": ["office=accountant", "office=tax_advisor"],
    "landscaper": ["craft=gardener", "craft=landscaper"],
    "painter": ["craft=painter"],
    "carpenter": ["craft=carpenter"],
    "locksmith": ["craft=locksmith", "shop=locksmith"]
}

class OsmOverpassProvider(BaseSearchProvider):
    """
    OpenStreetMap Overpass API Provider.
    Free, public, requires no API key. Permitted under ODbL.
    Provides verified business names, addresses, phones, and official websites.
    Does not provide subjective ratings or review counts (honestly returned as None).
    """

    OVERPASS_SERVERS = [
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
        "https://overpass-api.de/api/interpreter"
    ]
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

    def __init__(self, user_agent: str = "LeadPulseScraper/1.0 (https://leadpulse.app; research@leadpulse.app)", timeout: int = 15):
        super().__init__(name="OpenStreetMap Overpass")
        self.user_agent = user_agent
        self.timeout = timeout

    def _geocode_location(self, location: str) -> Optional[tuple]:
        """Geocodes a location to get bounding box or center (lat, lon)."""
        headers = {
            "User-Agent": "LeadPulseScraper/1.0 (https://leadpulse.app; research-contact@leadpulse.app)",
            "Accept": "application/json"
        }
        params = {
            "q": location,
            "format": "json",
            "limit": 1
        }
        try:
            resp = requests.get(self.NOMINATIM_URL, params=params, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    bbox = item.get("boundingbox")
                    if bbox and len(bbox) == 4:
                        s, n, w, e = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                        # Slightly broaden boundary to capture suburban commercial districts
                        pad = 0.04
                        return s - pad, n + pad, w - pad, e + pad
                    lat, lon = float(item["lat"]), float(item["lon"])
                    delta = 0.12
                    return lat - delta, lat + delta, lon - delta, lon + delta
        except Exception as e:
            self.logger.warning("Geocoding failed for %s: %s", location, e)
        return None

    def search(self, niche: str, location: str, limit: int = 20) -> List[LeadData]:
        bbox = self._geocode_location(location)
        if not bbox:
            self.logger.info("Could not resolve location coordinates for '%s'", location)
            return []

        min_lat, max_lat, min_lon, max_lon = bbox
        
        # Match niche keyword flexibly
        niche_lower = niche.lower().strip()
        tags = []
        for key, mapped_tags in NICHE_TAG_MAP.items():
            if key in niche_lower:
                tags.extend(mapped_tags)
                break
        
        if tags:
            tag_filter = "".join([f'node[{t}]({min_lat},{min_lon},{max_lat},{max_lon}); way[{t}]({min_lat},{min_lon},{max_lat},{max_lon}); ' for t in tags])
        else:
            first_word = niche_lower.split()[0] if niche_lower else ""
            tag_filter = (
                f'node["craft"]["name"~"{first_word}",i]({min_lat},{min_lon},{max_lat},{max_lon}); '
                f'node["shop"]["name"~"{first_word}",i]({min_lat},{min_lon},{max_lat},{max_lon}); '
                f'node["amenity"]["name"~"{first_word}",i]({min_lat},{min_lon},{max_lat},{max_lon}); '
                f'node["office"]["name"~"{first_word}",i]({min_lat},{min_lon},{max_lat},{max_lon}); '
                f'way["craft"]["name"~"{first_word}",i]({min_lat},{min_lon},{max_lat},{max_lon}); '
                f'way["shop"]["name"~"{first_word}",i]({min_lat},{min_lon},{max_lat},{max_lon}); '
            )

        overpass_query = f"""
        [out:json][timeout:15];
        (
          {tag_filter}
        );
        out tags center {limit};
        """

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json"
        }

        results: List[LeadData] = []
        for server in self.OVERPASS_SERVERS:
            try:
                resp = requests.post(
                    server,
                    data={"data": overpass_query},
                    headers=headers,
                    timeout=self.timeout
                )
                if resp.status_code == 429:
                    self.logger.warning("Overpass server %s rate-limited, trying next mirror", server)
                    time.sleep(1)
                    continue
                if resp.status_code != 200:
                    continue

                payload = resp.json()
                elements = payload.get("elements", [])
                for el in elements:
                    tags = el.get("tags", {})
                    name = tags.get("name")
                    if not name:
                        continue
                    
                    # Extract website
                    raw_website = tags.get("website") or tags.get("contact:website") or tags.get("url")
                    norm_url, domain, is_valid = DomainService.classify_and_resolve_url(raw_website)
                    
                    # Phone
                    phone = tags.get("phone") or tags.get("contact:phone")

                    # Address
                    addr_parts = [
                        tags.get("addr:housenumber"),
                        tags.get("addr:street"),
                        tags.get("addr:city") or location,
                        tags.get("addr:postcode")
                    ]
                    address = ", ".join([p for p in addr_parts if p]) or location

                    el_id = el.get("id")
                    el_type = el.get("type", "node")
                    source_url = f"https://www.openstreetmap.org/{el_type}/{el_id}"

                    lead = LeadData(
                        business_name=name.strip(),
                        category_or_niche=niche,
                        location=location,
                        rating=None,  # Honestly None: OSM does not maintain review scores
                        review_count=None,
                        website_url=norm_url if is_valid else (norm_url if raw_website else None),
                        website_domain=domain if is_valid else None,
                        source_name="OpenStreetMap (Overpass)",
                        source_url=source_url,
                        collection_status="live",
                        phone=phone,
                        address=address
                    )
                    results.append(lead)
                    if len(results) >= limit:
                        break
                
                if results:
                    break  # Success
            except requests.Timeout:
                self.logger.warning("Timeout querying Overpass mirror %s", server)
                continue
            except Exception as e:
                self.logger.error("Error from Overpass mirror %s: %s", server, e)
                continue

        return results
