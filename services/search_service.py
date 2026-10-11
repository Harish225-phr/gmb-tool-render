import uuid
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from config import Config
from providers.base import LeadData, BaseSearchProvider, ProviderError
from providers.osm_overpass import OsmOverpassProvider
from providers.public_search import PublicSearchProvider
from providers.public_directory import PublicDirectoryProvider
from services.deduplication_service import DeduplicationService
import logging

logger = logging.getLogger(__name__)

class SearchJob:
    """Represents a background search job across multiple locations."""

    def __init__(self, job_id: str, niche: str, locations: List[str], limit_per_location: int = 20):
        self.job_id = job_id
        self.niche = niche
        self.locations = locations
        self.limit_per_location = limit_per_location
        self.status = "queued"  # queued, running, completed, cancelled, failed
        self.current_location = ""
        self.completed_locations = 0
        self.failed_locations = 0
        self.total_locations = len(locations)
        self.leads: List[LeadData] = []
        self.errors: List[Dict[str, str]] = []
        self.cancelled = False
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        stats = DeduplicationService.calculate_summary_stats(self.leads)
        return {
            "job_id": self.job_id,
            "niche": self.niche,
            "total_locations": self.total_locations,
            "completed_locations": self.completed_locations,
            "failed_locations": self.failed_locations,
            "current_location": self.current_location,
            "status": self.status,
            "lead_count": len(self.leads),
            "errors": self.errors,
            "summary_stats": stats,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class SearchService:
    """Orchestrates search jobs, provider fallback, and background thread execution."""

    def __init__(self, config: Config):
        self.config = config
        self.jobs: Dict[str, SearchJob] = {}
        self.lock = threading.Lock()
        
        # Instantiate available providers with fast web search and deep OSM POIs
        self.providers: List[BaseSearchProvider] = [
            PublicSearchProvider(user_agent=config.USER_AGENT, timeout=config.REQUEST_TIMEOUT),
            OsmOverpassProvider(user_agent=config.USER_AGENT, timeout=config.REQUEST_TIMEOUT),
            PublicDirectoryProvider(user_agent=config.USER_AGENT, timeout=config.REQUEST_TIMEOUT)
        ]

    def create_job(self, niche: str, locations: List[str], limit_per_location: int = 20) -> SearchJob:
        """Creates and registers a new search job."""
        self._cleanup_old_jobs()
        job_id = str(uuid.uuid4())
        job = SearchJob(job_id, niche, locations, limit_per_location)
        with self.lock:
            self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[SearchJob]:
        with self.lock:
            return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job.status in ("queued", "running"):
                job.cancelled = True
                job.status = "cancelled"
                job.updated_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def start_job_async(self, job: SearchJob):
        """Starts worker thread for job execution."""
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()

    def _cleanup_old_jobs(self):
        """Removes expired jobs to avoid unbounded memory growth on Render."""
        now = time.time()
        with self.lock:
            to_delete = []
            for jid, j in self.jobs.items():
                try:
                    created_dt = datetime.fromisoformat(j.created_at)
                    if now - created_dt.timestamp() > self.config.JOB_RETENTION_SECONDS:
                        to_delete.append(jid)
                except Exception:
                    pass
            for jid in to_delete:
                del self.jobs[jid]

    def _run_job(self, job: SearchJob):
        """Worker executing sequential/paced location scraping to respect Render resources."""
        job.status = "running"
        job.updated_at = datetime.now(timezone.utc).isoformat()

        all_collected_leads: List[LeadData] = []

        for location in job.locations:
            if job.cancelled:
                job.status = "cancelled"
                break

            job.current_location = location
            job.updated_at = datetime.now(timezone.utc).isoformat()
            location_leads: List[LeadData] = []
            location_failed = True

            for provider in self.providers:
                if not provider.enabled or job.cancelled:
                    continue

                needed = max(5, job.limit_per_location - len(location_leads))
                try:
                    logger.info("Querying provider %s for '%s' in '%s' (needed: %d)", provider.name, job.niche, location, needed)
                    results = provider.search(job.niche, location, limit=needed)
                    if results:
                        location_leads.extend(results)
                        location_failed = False
                        # If we have reached or exceeded desired results, move to next location
                        if len(location_leads) >= job.limit_per_location:
                            break
                    
                    # Polite pause between provider queries
                    time.sleep(self.config.DELAY_BETWEEN_REQUESTS)

                except ProviderError as pe:
                    logger.warning("Provider error on %s for %s: %s", provider.name, location, pe)
                    job.errors.append({
                        "location": location,
                        "provider": provider.name,
                        "error": str(pe),
                        "blocked": pe.is_blocked
                    })
                    # If blocked, continue to next provider
                    continue
                except Exception as e:
                    logger.error("Unexpected error on %s for %s: %s", provider.name, location, e)
                    job.errors.append({
                        "location": location,
                        "provider": provider.name,
                        "error": str(e),
                        "blocked": False
                    })
                    continue

            if location_leads:
                # Deduplicate leads collected for this location
                deduped = DeduplicationService.deduplicate_leads(location_leads)
                all_collected_leads.extend(deduped)
                job.completed_locations += 1
            else:
                if location_failed:
                    job.failed_locations += 1
                else:
                    # Successfully searched but no results found
                    job.completed_locations += 1

            # Update job lead list so far for live progress view
            job.leads = all_collected_leads
            job.updated_at = datetime.now(timezone.utc).isoformat()

            # Slight delay before next location to prevent aggressive bursts
            if not job.cancelled:
                time.sleep(self.config.DELAY_BETWEEN_REQUESTS)

        if not job.cancelled:
            # Final deduplication across all results
            job.leads = DeduplicationService.deduplicate_leads(all_collected_leads)
            job.current_location = ""
            job.status = "completed" if job.completed_locations > 0 or not job.errors else "failed"
            job.updated_at = datetime.now(timezone.utc).isoformat()
