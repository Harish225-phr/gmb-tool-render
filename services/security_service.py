import ipaddress
import socket
import urllib.parse
from typing import Tuple, Optional, List
import requests
import logging

logger = logging.getLogger(__name__)

# Disallowed IP networks for SSRF protection
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),       # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),         # Loopback
    ipaddress.ip_network("169.254.0.0/16"),       # Link-local / Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),       # Private B
    ipaddress.ip_network("192.0.0.0/24"),        # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),        # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),      # Private C
    ipaddress.ip_network("198.18.0.0/15"),       # Benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),     # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),      # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),         # Multicast
    ipaddress.ip_network("240.0.0.0/4"),         # Reserved
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    # IPv6 blocked ranges
    ipaddress.ip_network("::/128"),              # Unspecified
    ipaddress.ip_network("::1/128"),             # Loopback
    ipaddress.ip_network("fc00::/7"),            # Unique local
    ipaddress.ip_network("fe80::/10"),           # Link-local
    ipaddress.ip_network("ff00::/8"),            # Multicast
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.platform.sh",
    "instance-data",
    "169.254.169.254"
}

class SecurityService:
    """Security utilities for input validation, SSRF defense, and CSV injection protection."""

    @classmethod
    def is_ip_blocked(cls, ip_str: str) -> bool:
        """Check if an IP address string belongs to a private, loopback, or cloud-metadata network."""
        try:
            ip = ipaddress.ip_address(ip_str)
            for network in BLOCKED_NETWORKS:
                if ip in network:
                    return True
            return False
        except ValueError:
            return True

    @classmethod
    def validate_url_safe(cls, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validates that a URL is safe to fetch (HTTP/HTTPS only, non-private, non-metadata).
        Resolves hostname DNS to verify IP addresses are not internal.
        """
        if not url:
            return False, "Empty URL"

        try:
            parsed = urllib.parse.urlsplit(url)
        except Exception:
            return False, "Malformed URL"

        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, f"Disallowed scheme: {scheme}. Only HTTP and HTTPS are permitted."

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False, "Missing hostname in URL."

        if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".local") or hostname.endswith(".internal"):
            return False, f"Access to restricted host '{hostname}' is blocked."

        # If hostname is an IP literal
        try:
            ip = ipaddress.ip_address(hostname)
            if cls.is_ip_blocked(str(ip)):
                return False, f"Direct access to private or reserved IP '{hostname}' is blocked."
            return True, None
        except ValueError:
            pass  # It's a domain name, resolve it

        # Resolve DNS
        try:
            addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
            if not addr_info:
                return False, f"Could not resolve host '{hostname}'."
            for family, _, _, _, sockaddr in addr_info:
                ip_resolved = sockaddr[0]
                if cls.is_ip_blocked(ip_resolved):
                    return False, f"Host '{hostname}' resolves to blocked private/local IP '{ip_resolved}'."
        except socket.gaierror:
            return False, f"DNS resolution failed for '{hostname}'."
        except Exception as e:
            return False, f"DNS resolution error: {str(e)}"

        return True, None

    @classmethod
    def safe_get_request(
        cls,
        url: str,
        timeout: int = 10,
        headers: Optional[dict] = None,
        max_bytes: int = 5 * 1024 * 1024
    ) -> requests.Response:
        """
        Fetches a URL safely with SSRF validation on the initial URL and each redirect target.
        Enforces maximum response size.
        """
        is_safe, error_msg = cls.validate_url_safe(url)
        if not is_safe:
            raise ValueError(f"SSRF Protection blocked request: {error_msg}")

        session = requests.Session()
        current_url = url
        redirect_hops = 0
        max_redirects = 5

        while redirect_hops <= max_redirects:
            resp = session.get(
                current_url,
                timeout=timeout,
                headers=headers,
                allow_redirects=False,
                stream=True
            )

            # Check status for redirect
            if 300 <= resp.status_code < 400 and "Location" in resp.headers:
                redirect_hops += 1
                next_url = urllib.parse.urljoin(current_url, resp.headers["Location"])
                is_safe, error_msg = cls.validate_url_safe(next_url)
                if not is_safe:
                    resp.close()
                    raise ValueError(f"SSRF Protection blocked redirect to {next_url}: {error_msg}")
                current_url = next_url
                continue
            
            # Read content up to max_bytes
            content = bytearray()
            for chunk in resp.iter_content(chunk_size=8192):
                content.extend(chunk)
                if len(content) > max_bytes:
                    resp.close()
                    raise ValueError(f"Response size exceeded {max_bytes} bytes limit.")
            
            # Attach safe content back to response
            resp._content = bytes(content)
            return resp

        raise ValueError(f"Exceeded maximum redirects ({max_redirects})")

    @classmethod
    def sanitize_for_spreadsheet(cls, text: Optional[str]) -> str:
        """
        Sanitizes text to prevent CSV/Spreadsheet Formula Injection.
        Formula injection chars: '=', '+', '-', '@', '\t', '\r' at start of cell.
        Prepends a single quote "'" if dangerous character detected.
        """
        if text is None:
            return ""
        s = str(text)
        if not s:
            return ""
        
        # Check if first character is dangerous
        first_char = s[0]
        if first_char in ("=", "+", "-", "@", "\t", "\r", "%"):
            return f"'{s}"
        return s

    @classmethod
    def validate_search_inputs(
        cls,
        niche: str,
        locations: List[str],
        limit_per_location: int
    ) -> Tuple[bool, Optional[str], str, List[str], int]:
        """Validates and cleans search parameters."""
        niche = (niche or "").strip()
        if not niche:
            return False, "Business niche is required.", "", [], 0
        if len(niche) > 100:
            return False, "Business niche cannot exceed 100 characters.", "", [], 0

        # Clean locations
        cleaned_locations: List[str] = []
        seen = set()
        for loc in locations:
            l = (loc or "").strip()
            if l and l.lower() not in seen:
                seen.add(l.lower())
                cleaned_locations.append(l)

        if not cleaned_locations:
            return False, "At least one valid location is required.", "", [], 0
        if len(cleaned_locations) > 30:
            return False, "Maximum 30 locations allowed per search to prevent server overload.", "", [], 0

        try:
            limit = int(limit_per_location)
            if limit < 1:
                limit = 10
            elif limit > 100:
                limit = 100
        except (ValueError, TypeError):
            limit = 20

        return True, None, niche, cleaned_locations, limit
