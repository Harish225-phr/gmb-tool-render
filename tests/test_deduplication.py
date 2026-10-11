import unittest
from providers.base import LeadData
from services.deduplication_service import DeduplicationService

class TestDeduplicationService(unittest.TestCase):

    def test_name_and_location_normalization(self):
        norm1 = DeduplicationService.normalize_name("Smith HVAC Solutions, LLC.")
        norm2 = DeduplicationService.normalize_name("Smith HVAC Solutions Inc")
        self.assertEqual(norm1, norm2)

        loc1 = DeduplicationService.normalize_location("Indianapolis, IN")
        loc2 = DeduplicationService.normalize_location("Indianapolis IN ")
        self.assertEqual(loc1, loc2)

    def test_deduplicate_leads_merges_richest(self):
        lead_partial = LeadData(
            business_name="Acme Plumbing",
            category_or_niche="plumber",
            location="Carmel, IN",
            rating=None,
            review_count=None,
            website_url=None,
            website_domain=None
        )
        lead_rich = LeadData(
            business_name="Acme Plumbing LLC",
            category_or_niche="plumber",
            location="Carmel, IN",
            rating=4.8,
            review_count=25,
            website_url="https://acmeplumbing.com",
            website_domain="acmeplumbing.com",
            phone="317-555-1234"
        )
        deduped = DeduplicationService.deduplicate_leads([lead_partial, lead_rich])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].website_domain, "acmeplumbing.com")
        self.assertEqual(deduped[0].rating, 4.8)
        self.assertEqual(deduped[0].phone, "317-555-1234")

    def test_cross_location_preservation(self):
        lead_indy = LeadData(
            business_name="Apex Roofing",
            category_or_niche="roofer",
            location="Indianapolis, IN",
            website_url=None,
            website_domain=None
        )
        lead_carmel = LeadData(
            business_name="Apex Roofing",
            category_or_niche="roofer",
            location="Carmel, IN",
            website_url=None,
            website_domain=None
        )
        # Without a common domain, distinct locations should remain distinct branches/listings
        deduped = DeduplicationService.deduplicate_leads([lead_indy, lead_carmel])
        self.assertEqual(len(deduped), 2)

    def test_summary_stats_honest_average_rating(self):
        leads = [
            LeadData(
                business_name="Rated High",
                category_or_niche="hvac",
                location="Indy",
                rating=5.0,
                review_count=10,
                website_url="https://site1.com",
                website_domain="site1.com"
            ),
            LeadData(
                business_name="Rated Lower",
                category_or_niche="hvac",
                location="Indy",
                rating=4.0,
                review_count=5,
                website_url="https://site2.com",
                website_domain="site2.com"
            ),
            LeadData(
                business_name="Unrated 1",
                category_or_niche="hvac",
                location="Indy",
                rating=None,  # Missing rating
                review_count=None,
                website_url=None,
                website_domain=None
            ),
            LeadData(
                business_name="Unrated 2",
                category_or_niche="hvac",
                location="Carmel",
                rating=None,  # Missing rating
                review_count=None,
                website_url=None,
                website_domain=None
            ),
        ]

        stats = DeduplicationService.calculate_summary_stats(leads)
        self.assertEqual(stats["total_records"], 4)
        self.assertEqual(stats["unique_domains"], 2)
        self.assertEqual(stats["businesses_without_websites"], 2)
        self.assertEqual(stats["missing_ratings_count"], 2)
        self.assertEqual(stats["valid_ratings_count"], 2)
        # Average must be (5.0 + 4.0) / 2 = 4.5. If missing were treated as zero, it would incorrectly be (9/4)=2.25.
        self.assertEqual(stats["average_rating"], 4.5)

    def test_summary_stats_all_unrated(self):
        leads = [
            LeadData(
                business_name="No Rating Biz",
                category_or_niche="electrician",
                location="Fishers",
                rating=None,
                review_count=None
            )
        ]
        stats = DeduplicationService.calculate_summary_stats(leads)
        self.assertIsNone(stats["average_rating"])
        self.assertEqual(stats["valid_ratings_count"], 0)

if __name__ == "__main__":
    unittest.main()
