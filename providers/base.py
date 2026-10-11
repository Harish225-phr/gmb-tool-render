import abc
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

@dataclass
class LeadData:
    business_name: str
    category_or_niche: str
    location: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    website_url: Optional[str] = None
    website_domain: Optional[str] = None
    source_name: str = ""
    source_url: str = ""
    collected_at: str = ""
    collection_status: str = "live"  # "live", "partial", "error"
    error_reason: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

    def __post_init__(self):
        if not self.collected_at:
            self.collected_at = datetime.now(timezone.utc).isoformat()
        if self.rating is not None:
            try:
                self.rating = round(float(self.rating), 1)
            except (ValueError, TypeError):
                self.rating = None
        if self.review_count is not None:
            try:
                self.review_count = int(self.review_count)
            except (ValueError, TypeError):
                self.review_count = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProviderError(Exception):
    """Exception raised when a provider encounters a blocking, rate-limit, or network issue."""
    def __init__(self, message: str, provider_name: str, is_blocked: bool = False):
        super().__init__(message)
        self.provider_name = provider_name
        self.is_blocked = is_blocked


class BaseSearchProvider(abc.ABC):
    """Abstract base class for all no-API-key search providers."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.logger = logging.getLogger(f"provider.{name}")

    @abc.abstractmethod
    def search(self, niche: str, location: str, limit: int = 20) -> List[LeadData]:
        """
        Execute search for a given niche and location.
        Returns a list of LeadData objects.
        Must NOT fabricate data or random ratings.
        Must set collection_status to 'live', 'partial', or 'error'.
        """
        pass
