import unittest
from providers.base import LeadData
from services.export_service import ExportService
from services.security_service import SecurityService

class TestExportService(unittest.TestCase):

    def test_csv_utf8_bom_and_headers(self):
        lead = LeadData(
            business_name="Indy Air Co.",
            category_or_niche="HVAC",
            location="Indianapolis, IN",
            rating=4.8,
            review_count=120,
            website_url="https://indyair.com",
            website_domain="indyair.com"
        )
        csv_str = ExportService.leads_to_csv_string([lead])
        self.assertTrue(csv_str.startswith('\ufeff'))
        self.assertIn("Business Name,Category,Location,Rating", csv_str)
        self.assertIn("Indy Air Co.", csv_str)
        self.assertIn("indyair.com", csv_str)

    def test_csv_formula_injection_defense(self):
        # Danger payloads that would execute in Excel / Calc
        malicious_lead = LeadData(
            business_name="=cmd|'/C calc'!A0",
            category_or_niche="+SUM(A1:A10)",
            location="-DANGEROUS",
            website_url="@https://evil.com",
            website_domain="\tmalicious.com"
        )
        csv_str = ExportService.leads_to_csv_string([malicious_lead], sanitize_formulas=True)
        # Should be escaped with leading single quote
        self.assertIn("'=cmd|'/C calc'!A0", csv_str)
        self.assertIn("'+SUM(A1:A10)", csv_str)
        self.assertIn("'-DANGEROUS", csv_str)
        self.assertIn("'@https://evil.com", csv_str)
        self.assertIn("'\tmalicious.com", csv_str)

    def test_csv_special_characters_escaping(self):
        lead = LeadData(
            business_name='Bob\'s "Super, Cool" HVAC\nHeating & Cooling',
            category_or_niche='HVAC',
            location='Noblesville, IN'
        )
        csv_str = ExportService.leads_to_csv_string([lead])
        # CSV writer should quote fields containing commas, quotes, or newlines
        self.assertIn('Bob\'s ""Super, Cool"" HVAC', csv_str)

    def test_leads_to_tsv_string(self):
        lead = LeadData(
            business_name="Greenwood Plumbing",
            category_or_niche="plumber",
            location="Greenwood, IN",
            rating=4.5,
            review_count=20,
            website_url="https://greenwoodplumb.com",
            website_domain="greenwoodplumb.com",
            phone="317-555-9999"
        )
        tsv_str = ExportService.leads_to_tsv_string([lead])
        lines = tsv_str.split("\n")
        self.assertEqual(len(lines), 2)
        cols = lines[1].split("\t")
        self.assertEqual(cols[0], "Greenwood Plumbing")
        self.assertEqual(cols[1], "Greenwood, IN")
        self.assertEqual(cols[2], "4.5")
        self.assertEqual(cols[3], "20")
        self.assertEqual(cols[4], "https://greenwoodplumb.com")
        self.assertEqual(cols[5], "greenwoodplumb.com")
        self.assertEqual(cols[6], "317-555-9999")

if __name__ == "__main__":
    unittest.main()
