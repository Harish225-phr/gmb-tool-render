import re
from typing import List, Dict, Any, Tuple, Optional
from providers.base import LeadData
import logging

logger = logging.getLogger(__name__)

# Legal and noise business name suffixes to strip for normalized comparison
BUSINESS_SUFFIXES = [
    r"\bllc\b", r"\binc\b", r"\bcorp\b", r"\bcorporation\b", r"\bco\b",
    r"\bcompany\b", r"\bltd\b", r"\blimited\b", r"\bpllc\b", r"\bpc\b",
    r"\bgroup\b", r"\bservices\b"
]

class DeduplicationService:
    """Service for lead deduplication, clustering, and summary statistics calculation."""

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalizes business name for deduplication comparison."""
        if not name:
            return ""
        s = name.lower().strip()
        # Remove legal suffixes
        for suffix in BUSINESS_SUFFIXES:
            s = re.sub(suffix, "", s, flags=re.IGNORECASE)
        # Remove punctuation and extra spaces
        s = re.sub(r"[^\w\s]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def normalize_location(loc: str) -> str:
        """Normalizes location string (e.g., 'Indianapolis, IN' -> 'indianapolis in')."""
        if not loc:
            return ""
        s = loc.lower().strip()
        s = re.sub(r"[^\w\s]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @classmethod
    def get_business_dedup_key(cls, lead: LeadData) -> str:
        """
        Calculates a unique business identity key.
        If domain exists, domain is the primary identity anchor.
        Otherwise, combines normalized business name and location.
        """
        if lead.website_domain:
            return f"domain:{lead.website_domain.lower()}"
        norm_name = cls.normalize_name(lead.business_name)
        norm_loc = cls.normalize_location(lead.location)
        return f"name_loc:{norm_name}::{norm_loc}"

    @classmethod
    def deduplicate_leads(cls, leads: List[LeadData]) -> List[LeadData]:
        """
        Deduplicates a list of leads while preserving the richest record.
        Matches by domain (if present) and normalized (name + location).
        """
        domain_map: Dict[str, LeadData] = {}
        name_loc_map: Dict[str, LeadData] = {}
        unique_leads: List[LeadData] = []

        for lead in leads:
            d_key = f"domain:{lead.website_domain.lower()}" if lead.website_domain else None
            nl_key = f"name_loc:{cls.normalize_name(lead.business_name)}::{cls.normalize_location(lead.location)}"

            existing: Optional[LeadData] = None
            if d_key and d_key in domain_map:
                existing = domain_map[d_key]
            elif nl_key in name_loc_map:
                existing = name_loc_map[nl_key]

            if existing:
                # Merge / keep richest lead
                if not existing.website_url and lead.website_url:
                    existing.website_url = lead.website_url
                    existing.website_domain = lead.website_domain
                if existing.rating is None and lead.rating is not None:
                    existing.rating = lead.rating
                if existing.review_count is None and lead.review_count is not None:
                    existing.review_count = lead.review_count
                if not existing.phone and lead.phone:
                    existing.phone = lead.phone
                if not existing.address and lead.address:
                    existing.address = lead.address
                # Link maps
                if existing.website_domain:
                    domain_map[f"domain:{existing.website_domain.lower()}"] = existing
                name_loc_map[nl_key] = existing
            else:
                unique_leads.append(lead)
                if d_key:
                    domain_map[d_key] = lead
                name_loc_map[nl_key] = lead

        return unique_leads

    @classmethod
    def extract_unique_domains(cls, leads: List[LeadData]) -> List[str]:
        """Returns sorted unique non-empty registrable domains."""
        domains = set()
        for lead in leads:
            if lead.website_domain:
                domains.add(lead.website_domain.lower())
        return sorted(list(domains))

    @classmethod
    def extract_unique_websites(cls, leads: List[LeadData]) -> List[str]:
        """Returns sorted unique non-empty normalized website URLs."""
        urls = set()
        for lead in leads:
            if lead.website_url:
                urls.add(lead.website_url)
        return sorted(list(urls))

    @classmethod
    def calculate_summary_stats(cls, leads: List[LeadData]) -> Dict[str, Any]:
        """
        Calculates honest summary metrics across leads.
        CRITICAL: Never treat missing ratings as zero when computing average rating!
        """
        total_records = len(leads)
        unique_domains_set = set()
        unique_businesses_set = set()
        no_website_count = 0
        missing_rating_count = 0
        missing_review_count = 0
        valid_ratings: List[float] = []

        for lead in leads:
            # Domain check
            if lead.website_domain:
                unique_domains_set.add(lead.website_domain.lower())
            
            # Website presence
            if not lead.website_url:
                no_website_count += 1

            # Business identity
            b_key = cls.get_business_dedup_key(lead)
            unique_businesses_set.add(b_key)

            # Rating
            if lead.rating is not None:
                valid_ratings.append(lead.rating)
            else:
                missing_rating_count += 1

            # Review count
            if lead.review_count is None:
                missing_review_count += 1

        avg_rating: Optional[float] = None
        if valid_ratings:
            avg_rating = round(sum(valid_ratings) / len(valid_ratings), 2)

        return {
            "total_records": total_records,
            "unique_businesses": len(unique_businesses_set),
            "unique_domains": len(unique_domains_set),
            "businesses_without_websites": no_website_count,
            "missing_ratings_count": missing_rating_count,
            "missing_reviews_count": missing_review_count,
            "valid_ratings_count": len(valid_ratings),
            "average_rating": avg_rating
        }
