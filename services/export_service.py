import io
import csv
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from providers.base import LeadData
from services.security_service import SecurityService

class ExportService:
    """Service for generating CSV exports with UTF-8 BOM, formula injection defense, and TSV clipboard texts."""

    CSV_HEADERS = [
        "Business Name",
        "Category",
        "Location",
        "Rating",
        "Reviews",
        "Website URL",
        "Website Domain",
        "Has Website",
        "Phone",
        "Address",
        "Source Name",
        "Source URL",
        "Collection Status",
        "Collected At"
    ]

    @classmethod
    def leads_to_csv_string(cls, leads: List[LeadData], sanitize_formulas: bool = True) -> str:
        """
        Converts a list of LeadData objects into CSV format string.
        Includes UTF-8 BOM for Microsoft Excel / spreadsheet compatibility.
        Protects against formula injection.
        """
        output = io.StringIO()
        # Note: If writing as string, we can prepend BOM character \ufeff
        output.write('\ufeff')
        
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(cls.CSV_HEADERS)

        for lead in leads:
            b_name = lead.business_name
            cat = lead.category_or_niche
            loc = lead.location
            rating = str(lead.rating) if lead.rating is not None else ""
            reviews = str(lead.review_count) if lead.review_count is not None else ""
            w_url = lead.website_url or ""
            w_domain = lead.website_domain or ""
            has_website = "Yes" if lead.website_url else "No"
            phone = lead.phone or ""
            address = lead.address or ""
            src_name = lead.source_name
            src_url = lead.source_url
            status = lead.collection_status
            collected_at = lead.collected_at

            if sanitize_formulas:
                row = [
                    SecurityService.sanitize_for_spreadsheet(b_name),
                    SecurityService.sanitize_for_spreadsheet(cat),
                    SecurityService.sanitize_for_spreadsheet(loc),
                    rating,
                    reviews,
                    SecurityService.sanitize_for_spreadsheet(w_url),
                    SecurityService.sanitize_for_spreadsheet(w_domain),
                    has_website,
                    SecurityService.sanitize_for_spreadsheet(phone),
                    SecurityService.sanitize_for_spreadsheet(address),
                    SecurityService.sanitize_for_spreadsheet(src_name),
                    SecurityService.sanitize_for_spreadsheet(src_url),
                    status,
                    collected_at
                ]
            else:
                row = [
                    b_name, cat, loc, rating, reviews, w_url, w_domain,
                    has_website, phone, address, src_name, src_url, status, collected_at
                ]
            writer.writerow(row)

        return output.getvalue()

    @classmethod
    def domains_to_csv_string(cls, domains: List[str], sanitize_formulas: bool = True) -> str:
        """Exports unique website domains to CSV."""
        output = io.StringIO()
        output.write('\ufeff')
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["Website Domain"])
        for d in domains:
            val = SecurityService.sanitize_for_spreadsheet(d) if sanitize_formulas else d
            writer.writerow([val])
        return output.getvalue()

    @classmethod
    def leads_to_tsv_string(cls, leads: List[LeadData]) -> str:
        """
        Converts leads into Tab-Separated Values (TSV) for direct paste into Excel/Google Sheets.
        """
        lines = []
        headers = ["Business Name", "Location", "Rating", "Reviews", "Website URL", "Website Domain", "Phone"]
        lines.append("\t".join(headers))

        for lead in leads:
            row = [
                lead.business_name or "",
                lead.location or "",
                str(lead.rating) if lead.rating is not None else "",
                str(lead.review_count) if lead.review_count is not None else "",
                lead.website_url or "",
                lead.website_domain or "",
                lead.phone or ""
            ]
            lines.append("\t".join(row))

        return "\n".join(lines)

    @classmethod
    def generate_export_filename(cls, prefix: str = "leads_export") -> str:
        """Generates a safe timestamped filename."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{ts}.csv"
