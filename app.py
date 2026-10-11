import os
import logging
from flask import Flask, render_template, request, jsonify, Response, send_file
from config import Config
from services.search_service import SearchService
from services.security_service import SecurityService
from services.export_service import ExportService
from services.deduplication_service import DeduplicationService
from providers.base import LeadData

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app")

app = Flask(__name__)
app.config.from_object(Config)

search_service = SearchService(Config)

# Clear distinction: Sample data for development / demo preview
SAMPLE_LEADS = [
    LeadData(
        business_name="Indy Premier HVAC & Air Solutions",
        category_or_niche="HVAC contractors",
        location="Indianapolis, IN",
        rating=4.9,
        review_count=138,
        website_url="https://indypremierhvac.com",
        website_domain="indypremierhvac.com",
        source_name="OpenStreetMap (Overpass)",
        source_url="https://www.openstreetmap.org/node/1029384",
        collection_status="sample",
        phone="(317) 555-0192",
        address="1024 Meridian St, Indianapolis, IN 46204"
    ),
    LeadData(
        business_name="Carmel Comfort Heating & Air",
        category_or_niche="HVAC contractors",
        location="Carmel, IN",
        rating=4.7,
        review_count=84,
        website_url="https://carmelcomfortair.com",
        website_domain="carmelcomfortair.com",
        source_name="DuckDuckGo HTML Search",
        source_url="https://html.duckduckgo.com/html/?q=HVAC+Carmel+IN",
        collection_status="sample",
        phone="(317) 555-0144",
        address="350 Range Line Rd, Carmel, IN 46032"
    ),
    LeadData(
        business_name="Hoosier State Mechanical",
        category_or_niche="HVAC contractors",
        location="Fishers, IN",
        rating=None,  # Real-world missing rating demonstration
        review_count=None,
        website_url=None,  # Lead with no website!
        website_domain=None,
        source_name="OpenStreetMap (Overpass)",
        source_url="https://www.openstreetmap.org/node/9948271",
        collection_status="sample",
        phone="(317) 555-0188",
        address="8900 E 116th St, Fishers, IN 46038"
    ),
    LeadData(
        business_name="Noblesville Thermal Systems LLC",
        category_or_niche="HVAC contractors",
        location="Noblesville, IN",
        rating=4.8,
        review_count=42,
        website_url="https://noblesvillethermal.com",
        website_domain="noblesvillethermal.com",
        source_name="YellowPages Directory",
        source_url="https://www.yellowpages.com/search?search_terms=HVAC&geo_location_terms=Noblesville+IN",
        collection_status="sample",
        phone="(317) 555-0129",
        address="198 S 10th St, Noblesville, IN 46060"
    ),
    LeadData(
        business_name="Midwest Air Specialists",
        category_or_niche="HVAC contractors",
        location="Greenwood, IN",
        rating=None,
        review_count=None,
        website_url=None,  # Another business without website
        website_domain=None,
        source_name="OpenStreetMap (Overpass)",
        source_url="https://www.openstreetmap.org/node/8821940",
        collection_status="sample",
        phone="(317) 555-0155",
        address="400 S State Rd 135, Greenwood, IN 46142"
    )
]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/favicon.ico")
def favicon():
    """Serves a clean SVG favicon to avoid browser 404 console errors."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="14" fill="#0d6efd"/><path d="M16 8v16M8 16h16" stroke="#ffffff" stroke-width="3" stroke-linecap="round"/></svg>'
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})

@app.route("/health")
@app.route("/api/health")
def health():
    """Health check endpoint for Render zero-downtime monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "lead-scraper",
        "active_jobs": len(search_service.jobs)
    })

@app.route("/api/search", methods=["POST"])
def start_search():
    """Starts a multi-location asynchronous scraping job."""
    data = request.get_json(silent=True) or {}
    niche = data.get("niche", "")
    locations_input = data.get("locations", [])
    limit_per_location = data.get("limit_per_location", Config.DEFAULT_LIMIT_PER_LOCATION)

    # Handle string or list of locations
    if isinstance(locations_input, str):
        locations_list = [line.strip() for line in locations_input.splitlines() if line.strip()]
    elif isinstance(locations_input, list):
        locations_list = [str(loc).strip() for loc in locations_input if str(loc).strip()]
    else:
        locations_list = []

    is_valid, err_msg, clean_niche, clean_locs, clean_limit = SecurityService.validate_search_inputs(
        niche, locations_list, limit_per_location
    )

    if not is_valid:
        return jsonify({"success": False, "error": err_msg}), 400

    job = search_service.create_job(clean_niche, clean_locs, clean_limit)
    search_service.start_job_async(job)

    return jsonify({
        "success": True,
        "job_id": job.job_id,
        "niche": job.niche,
        "total_locations": job.total_locations,
        "status": job.status
    })

@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id: str):
    """Retrieves status and results for a search job."""
    job = search_service.get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found or expired"}), 404

    job_dict = job.to_dict()
    job_dict["leads"] = [lead.to_dict() for lead in job.leads]
    return jsonify({"success": True, "data": job_dict})

@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id: str):
    """Cancels a running search job."""
    cancelled = search_service.cancel_job(job_id)
    return jsonify({"success": cancelled})

@app.route("/api/sample-data", methods=["GET"])
def get_sample_data():
    """Returns clearly labeled sample data for UI development and verification."""
    stats = DeduplicationService.calculate_summary_stats(SAMPLE_LEADS)
    return jsonify({
        "success": True,
        "is_sample": True,
        "data": {
            "job_id": "sample-demo-job",
            "niche": "HVAC contractors",
            "total_locations": 5,
            "completed_locations": 5,
            "failed_locations": 0,
            "current_location": "",
            "status": "completed",
            "lead_count": len(SAMPLE_LEADS),
            "errors": [],
            "summary_stats": stats,
            "leads": [lead.to_dict() for lead in SAMPLE_LEADS]
        }
    })

@app.route("/api/export/csv", methods=["POST"])
def export_csv():
    """
    Exports leads to CSV with UTF-8 BOM and formula injection protection.
    Accepts:
      - job_id: id of the job (or 'sample' for sample data)
      - export_type: 'all', 'selected', 'domains', 'no_websites', 'filtered'
      - leads_data: optional array of leads directly from client-side filtered view
    """
    payload = request.get_json(silent=True) or {}
    job_id = payload.get("job_id")
    export_type = payload.get("export_type", "all")
    client_leads = payload.get("leads_data")

    leads: list[LeadData] = []

    if client_leads and isinstance(client_leads, list):
        for item in client_leads:
            leads.append(LeadData(
                business_name=item.get("business_name", ""),
                category_or_niche=item.get("category_or_niche", ""),
                location=item.get("location", ""),
                rating=item.get("rating"),
                review_count=item.get("review_count"),
                website_url=item.get("website_url"),
                website_domain=item.get("website_domain"),
                source_name=item.get("source_name", ""),
                source_url=item.get("source_url", ""),
                collected_at=item.get("collected_at", ""),
                collection_status=item.get("collection_status", "live"),
                phone=item.get("phone"),
                address=item.get("address")
            ))
    elif job_id == "sample-demo-job" or job_id == "sample":
        leads = SAMPLE_LEADS
    elif job_id:
        job = search_service.get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        leads = job.leads

    # Filter based on export_type
    if export_type == "no_websites":
        filtered = [l for l in leads if not l.website_url]
        csv_content = ExportService.leads_to_csv_string(filtered)
        filename = ExportService.generate_export_filename("no_website_leads")
    elif export_type == "domains":
        domains = DeduplicationService.extract_unique_domains(leads)
        csv_content = ExportService.domains_to_csv_string(domains)
        filename = ExportService.generate_export_filename("unique_domains")
    elif export_type == "unique_websites":
        # Filter leads to unique website records
        seen_domains = set()
        unique_leads = []
        for l in leads:
            if l.website_domain and l.website_domain.lower() not in seen_domains:
                seen_domains.add(l.website_domain.lower())
                unique_leads.append(l)
        csv_content = ExportService.leads_to_csv_string(unique_leads)
        filename = ExportService.generate_export_filename("unique_website_leads")
    else:
        # 'all' or 'selected' or 'filtered'
        csv_content = ExportService.leads_to_csv_string(leads)
        filename = ExportService.generate_export_filename("leads")

    return Response(
        csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache"
        }
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", Config.PORT))
    logger.info("Starting Lead Scraper server on %s:%s", Config.HOST, port)
    app.run(host=Config.HOST, port=port, debug=Config.DEBUG)
