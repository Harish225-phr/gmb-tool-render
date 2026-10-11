import unittest
from unittest.mock import patch, MagicMock
import requests
from config import Config
from providers.base import LeadData, ProviderError, BaseSearchProvider
from providers.public_search import PublicSearchProvider
from providers.osm_overpass import OsmOverpassProvider
from services.search_service import SearchService, SearchJob

# Realistic HTML Fixture for DuckDuckGo
MOCK_DDG_HTML = """
<!DOCTYPE html>
<html>
<body>
  <div class="result web-result">
    <h2 class="result__title">
      <a class="result__url result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.indycomfortcooling.com%2Fabout">
        Indy Comfort Heating & Air | Indianapolis, IN
      </a>
    </h2>
    <div class="result__snippet">
      Top rated residential HVAC contractors in Indianapolis. Rated 4.9 stars with 142 reviews. Emergency 24/7 service.
    </div>
  </div>

  <div class="result web-result">
    <h2 class="result__title">
      <a class="result__url result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fyelp.com%2Fbiz%2Findy-cooling">
        Directory Listing on Yelp - Indy Cooling
      </a>
    </h2>
    <div class="result__snippet">
      Directory page with reviews and listings.
    </div>
  </div>
</body>
</html>
"""

# Realistic JSON Fixture for Overpass
MOCK_OVERPASS_JSON = {
    "elements": [
        {
            "type": "node",
            "id": 123456,
            "tags": {
                "name": "Hoosier HVAC & Plumbing",
                "craft": "hvac",
                "website": "https://hoosierhvac.com",
                "phone": "(317) 555-4321",
                "addr:city": "Carmel",
                "addr:street": "Main St",
                "addr:housenumber": "200"
            }
        },
        {
            "type": "node",
            "id": 789012,
            "tags": {
                "name": "Carmel Heating Co",
                "craft": "hvac",
                # No website tag
                "phone": "(317) 555-8765"
            }
        }
    ]
}

class TestSearchProviders(unittest.TestCase):

    @patch("requests.post")
    def test_duckduckgo_provider_parsing(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_DDG_HTML
        mock_post.return_value = mock_resp

        provider = PublicSearchProvider()
        results = provider.search("HVAC", "Indianapolis, IN", limit=10)

        self.assertEqual(len(results), 2)
        lead = results[0]
        self.assertEqual(lead.business_name, "Indy Comfort Heating & Air")
        self.assertEqual(lead.website_domain, "indycomfortcooling.com")
        self.assertEqual(lead.rating, 4.9)
        self.assertEqual(lead.review_count, 142)

        # Second result is Yelp (directory domain)
        yelp_lead = results[1]
        self.assertIsNone(yelp_lead.website_domain)  # Directory domain excluded as official business website
        self.assertIsNone(yelp_lead.website_url)

    @patch("requests.post")
    def test_duckduckgo_provider_blocked_handling(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        provider = PublicSearchProvider()
        with self.assertRaises(ProviderError) as ctx:
            provider.search("HVAC", "Indianapolis, IN")
        self.assertTrue(ctx.exception.is_blocked)

    @patch("requests.post")
    @patch("requests.get")
    def test_overpass_provider_parsing(self, mock_get, mock_post):
        # Mock Nominatim geocoding
        mock_geo_resp = MagicMock()
        mock_geo_resp.status_code = 200
        mock_geo_resp.json.return_value = [{"boundingbox": ["39.9", "40.0", "-86.2", "-86.0"]}]
        mock_get.return_value = mock_geo_resp

        # Mock Overpass interpreter
        mock_overpass_resp = MagicMock()
        mock_overpass_resp.status_code = 200
        mock_overpass_resp.json.return_value = MOCK_OVERPASS_JSON
        mock_post.return_value = mock_overpass_resp

        provider = OsmOverpassProvider()
        results = provider.search("HVAC", "Carmel, IN", limit=10)

        self.assertEqual(len(results), 2)
        lead1 = results[0]
        self.assertEqual(lead1.business_name, "Hoosier HVAC & Plumbing")
        self.assertEqual(lead1.website_domain, "hoosierhvac.com")
        self.assertEqual(lead1.phone, "(317) 555-4321")
        self.assertIsNone(lead1.rating)  # Honestly None: OSM has no reviews

        # Lead without website
        lead2 = results[1]
        self.assertEqual(lead2.business_name, "Carmel Heating Co")
        self.assertIsNone(lead2.website_url)
        self.assertIsNone(lead2.website_domain)

    def test_search_pipeline_partial_failure_resilience(self):
        """
        Verify that if location 1 fails completely, location 2 still succeeds
        and its leads are preserved in the job results without wiping.
        """
        config = Config()
        config.DELAY_BETWEEN_REQUESTS = 0.0
        service = SearchService(config)

        # Create a mock provider where Location 1 fails but Location 2 succeeds
        mock_provider = MagicMock(spec=BaseSearchProvider)
        mock_provider.name = "MockProvider"
        mock_provider.enabled = True

        def mock_search_fn(niche, location, limit=20):
            if "BadCity" in location:
                raise ProviderError("Network error on BadCity", "MockProvider", is_blocked=False)
            return [
                LeadData(
                    business_name="Good Plumbing",
                    category_or_niche=niche,
                    location=location,
                    website_url="https://goodplumbing.com",
                    website_domain="goodplumbing.com"
                )
            ]

        mock_provider.search.side_effect = mock_search_fn
        service.providers = [mock_provider]

        job = service.create_job("plumber", ["BadCity, IN", "GoodCity, IN"], limit_per_location=10)
        # Run synchronously for test
        service._run_job(job)

        self.assertEqual(job.total_locations, 2)
        self.assertEqual(job.completed_locations, 1)
        self.assertEqual(job.failed_locations, 1)
        self.assertEqual(len(job.leads), 1)
        self.assertEqual(job.leads[0].business_name, "Good Plumbing")
        self.assertEqual(len(job.errors), 1)
        self.assertEqual(job.errors[0]["location"], "BadCity, IN")

if __name__ == "__main__":
    unittest.main()
