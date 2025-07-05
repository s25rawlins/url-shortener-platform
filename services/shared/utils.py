import string
import secrets
import hashlib
import re
from typing import Optional
from urllib.parse import urlparse
from user_agents import parse as parse_user_agent


def generate_short_code(length: int = 6) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def encode_base62(num: int) -> str:
    if num == 0:
        return "0"
    
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    base62 = ""
    
    while num:
        num, remainder = divmod(num, 62)
        base62 = alphabet[remainder] + base62
    
    return base62


def decode_base62(base62_str: str) -> int:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    num = 0
    
    for char in base62_str:
        num = num * 62 + alphabet.index(char)
    
    return num


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def normalize_url(url: str) -> str:
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def is_valid_short_code(code: str) -> bool:
    if not code or len(code) > 10:
        return False
    return re.match(r'^[a-zA-Z0-9]+$', code) is not None


def hash_ip_address(ip: str, salt: str = "") -> str:
    return hashlib.sha256((ip + salt).encode()).hexdigest()[:16]


def parse_user_agent_info(user_agent: str) -> dict:
    try:
        ua = parse_user_agent(user_agent)
        return {
            "browser": f"{ua.browser.family} {ua.browser.version_string}",
            "os": f"{ua.os.family} {ua.os.version_string}",
            "device_type": ua.device.family if ua.device.family != "Other" else "Desktop",
            "is_mobile": ua.is_mobile,
            "is_tablet": ua.is_tablet,
            "is_bot": ua.is_bot,
        }
    except Exception:
        return {
            "browser": "Unknown",
            "os": "Unknown",
            "device_type": "Unknown",
            "is_mobile": False,
            "is_tablet": False,
            "is_bot": False,
        }


def get_client_ip(request) -> Optional[str]:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    if hasattr(request, 'client') and request.client:
        return request.client.host
    
    return None


def extract_domain(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return None


def is_safe_redirect_url(url: str, allowed_domains: Optional[list] = None) -> bool:
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme or not parsed.netloc:
            return False
        
        if parsed.scheme not in ['http', 'https']:
            return False
        
        if allowed_domains:
            domain = parsed.netloc.lower()
            return any(domain.endswith(allowed) for allowed in allowed_domains)
        
        return True
    except Exception:
        return False


def sanitize_metadata(metadata: dict, max_size: int = 1000) -> dict:
    if not isinstance(metadata, dict):
        return {}
    
    import json
    try:
        json_str = json.dumps(metadata, default=str)
        if len(json_str) > max_size:
            return {"error": "metadata_too_large", "original_size": len(json_str)}
        return metadata
    except Exception:
        return {"error": "invalid_metadata"}


def get_country_from_ip(ip: str) -> Optional[str]:
    # TODO: integrate with GeoIP service
    return None


def get_city_from_ip(ip: str) -> Optional[str]:
    # TODO: integrate with GeoIP service
    return None


def format_analytics_data(data: dict) -> dict:
    formatted = {}
    
    for key, value in data.items():
        if isinstance(value, (int, float)):
            formatted[key] = value
        elif isinstance(value, str):
            formatted[key] = value
        elif isinstance(value, list):
            formatted[key] = value[:10]
        else:
            formatted[key] = str(value)
    
    return formatted


def create_short_url(base_url: str, short_code: str) -> str:
    base_url = base_url.rstrip('/')
    return f"{base_url}/{short_code}"


def validate_custom_code(code: str, min_length: int = 3, max_length: int = 10) -> tuple[bool, str]:
    if not code:
        return False, "Code cannot be empty"
    
    if len(code) < min_length:
        return False, f"Code must be at least {min_length} characters"
    
    if len(code) > max_length:
        return False, f"Code must be at most {max_length} characters"
    
    if not is_valid_short_code(code):
        return False, "Code can only contain letters and numbers"
    
    reserved_words = ['api', 'admin', 'www', 'app', 'health', 'metrics', 'docs']
    if code.lower() in reserved_words:
        return False, "Code is reserved"
    
    return True, "Valid"
