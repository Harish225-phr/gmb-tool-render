import unittest
from services.domain_service import DomainService

class TestDomainService(unittest.TestCase):

    def test_clean_and_normalize_url_basic(self):
        url = "http://example.com/services"
        normalized = DomainService.clean_and_normalize_url(url)
        self.assertEqual(normalized, "http://example.com/services")

    def test_clean_and_normalize_url_add_scheme(self):
        url = "example.com/contact"
        normalized = DomainService.clean_and_normalize_url(url)
        self.assertEqual(normalized, "https://example.com/contact")

    def test_clean_and_normalize_url_strip_tracking(self):
        url = "https://www.example.com/about?utm_source=google&utm_medium=cpc&fbclid=12345&real_param=active"
        normalized = DomainService.clean_and_normalize_url(url)
        self.assertNotIn("utm_source", normalized)
        self.assertNotIn("fbclid", normalized)
        self.assertIn("real_param=active", normalized)

    def test_clean_and_normalize_url_strip_fragment(self):
        url = "https://example.com/services#reviews"
        normalized = DomainService.clean_and_normalize_url(url)
        self.assertEqual(normalized, "https://example.com/services")

    def test_invalid_urls_and_email(self):
        self.assertIsNone(DomainService.clean_and_normalize_url("mailto:info@business.com"))
        self.assertIsNone(DomainService.clean_and_normalize_url("info@business.com"))
        self.assertIsNone(DomainService.clean_and_normalize_url(""))
        self.assertIsNone(DomainService.clean_and_normalize_url(None))
        self.assertIsNone(DomainService.clean_and_normalize_url("ftp://ftp.example.com"))

    def test_extract_registrable_domain(self):
        self.assertEqual(DomainService.extract_registrable_domain("https://www.example.com/about"), "example.com")
        self.assertEqual(DomainService.extract_registrable_domain("https://sub.blog.example.com"), "example.com")
        self.assertEqual(DomainService.extract_registrable_domain("http://plumbing-pros.co.uk/services"), "plumbing-pros.co.uk")
        self.assertEqual(DomainService.extract_registrable_domain("carmelhvac.com"), "carmelhvac.com")

    def test_subdomain_preservation_in_original_vs_domain(self):
        norm_url, domain, is_valid = DomainService.classify_and_resolve_url("https://service.indyhvac.com/about")
        # Subdomain preserved in URL
        self.assertEqual(norm_url, "https://service.indyhvac.com/about")
        # Domain extracted as registrable domain
        self.assertEqual(domain, "indyhvac.com")
        self.assertTrue(is_valid)

    def test_social_and_directory_filtering(self):
        self.assertTrue(DomainService.is_social_or_directory("https://www.facebook.com/indyplumber"))
        self.assertTrue(DomainService.is_social_or_directory("https://yelp.com/biz/indy-hvac"))
        self.assertTrue(DomainService.is_social_or_directory("https://www.yellowpages.com/carmel-in/mip/123"))

        _, _, is_valid_fb = DomainService.classify_and_resolve_url("https://www.facebook.com/mybiz")
        self.assertFalse(is_valid_fb)

        _, _, is_valid_real = DomainService.classify_and_resolve_url("https://smithheatingandcooling.com")
        self.assertTrue(is_valid_real)

if __name__ == "__main__":
    unittest.main()
