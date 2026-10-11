import unittest
from services.security_service import SecurityService

class TestSecurityService(unittest.TestCase):

    def test_ssrf_blocks_private_and_loopback_ips(self):
        # Loopback
        self.assertTrue(SecurityService.is_ip_blocked("127.0.0.1"))
        self.assertTrue(SecurityService.is_ip_blocked("127.0.0.2"))
        self.assertTrue(SecurityService.is_ip_blocked("::1"))

        # Cloud Metadata (AWS, GCP, Azure, DigitalOcean)
        self.assertTrue(SecurityService.is_ip_blocked("169.254.169.254"))

        # Private ranges
        self.assertTrue(SecurityService.is_ip_blocked("10.0.0.1"))
        self.assertTrue(SecurityService.is_ip_blocked("192.168.1.1"))
        self.assertTrue(SecurityService.is_ip_blocked("172.16.0.50"))
        self.assertTrue(SecurityService.is_ip_blocked("0.0.0.0"))

    def test_ssrf_validate_url_safe(self):
        # Localhost URL
        safe, msg = SecurityService.validate_url_safe("http://localhost:8080/admin")
        self.assertFalse(safe)
        self.assertIn("restricted host", msg.lower())

        # Direct metadata IP URL
        safe, msg = SecurityService.validate_url_safe("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)

        # Disallowed schemes
        safe, msg = SecurityService.validate_url_safe("ftp://example.com")
        self.assertFalse(safe)
        self.assertIn("disallowed scheme", msg.lower())

        safe, msg = SecurityService.validate_url_safe("file:///etc/passwd")
        self.assertFalse(safe)

    def test_input_validation(self):
        # Empty niche
        valid, err, _, _, _ = SecurityService.validate_search_inputs("", ["Indy, IN"], 20)
        self.assertFalse(valid)
        self.assertIn("niche is required", err.lower())

        # Empty locations
        valid, err, _, _, _ = SecurityService.validate_search_inputs("HVAC", ["", "  "], 20)
        self.assertFalse(valid)
        self.assertIn("at least one valid location", err.lower())

        # Cleaning and deduplicating locations
        valid, err, niche, locs, limit = SecurityService.validate_search_inputs(
            " plumbers ",
            ["Carmel, IN", " carmel, in ", "Fishers, IN", ""],
            -5
        )
        self.assertTrue(valid)
        self.assertEqual(niche, "plumbers")
        self.assertEqual(len(locs), 2)  # Carmel deduplicated case-insensitively
        self.assertEqual(locs[0], "Carmel, IN")
        self.assertEqual(locs[1], "Fishers, IN")
        self.assertEqual(limit, 10)  # Negative limit normalized

    def test_formula_injection_sanitization(self):
        self.assertEqual(SecurityService.sanitize_for_spreadsheet("=1+1"), "'=1+1")
        self.assertEqual(SecurityService.sanitize_for_spreadsheet("+SUM(A1:A5)"), "'+SUM(A1:A5)")
        self.assertEqual(SecurityService.sanitize_for_spreadsheet("-10"), "'-10")
        self.assertEqual(SecurityService.sanitize_for_spreadsheet("@mention"), "'@mention")
        self.assertEqual(SecurityService.sanitize_for_spreadsheet("\tindented"), "'\tindented")
        self.assertEqual(SecurityService.sanitize_for_spreadsheet("Normal Business"), "Normal Business")
        self.assertEqual(SecurityService.sanitize_for_spreadsheet(""), "")
        self.assertEqual(SecurityService.sanitize_for_spreadsheet(None), "")

if __name__ == "__main__":
    unittest.main()
