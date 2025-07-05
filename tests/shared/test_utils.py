"""Tests for shared utility functions."""

import pytest
from unittest.mock import Mock, patch
from services.shared.utils import (
    generate_short_code,
    encode_base62,
    decode_base62,
    is_valid_url,
    normalize_url,
    is_valid_short_code,
    hash_ip_address,
    parse_user_agent_info,
    get_client_ip,
    extract_domain,
    is_safe_redirect_url,
    sanitize_metadata,
    create_short_url,
    validate_custom_code,
)


class TestShortCodeGeneration:
    """Test short code generation functions."""

    def test_generate_short_code_default_length(self):
        """Test generating short code with default length."""
        code = generate_short_code()
        assert len(code) == 6
        assert code.isalnum()

    def test_generate_short_code_custom_length(self):
        """Test generating short code with custom length."""
        code = generate_short_code(10)
        assert len(code) == 10
        assert code.isalnum()

    def test_generate_short_code_uniqueness(self):
        """Test that generated codes are unique."""
        codes = [generate_short_code() for _ in range(100)]
        assert len(set(codes)) == len(codes)  # All codes should be unique


class TestBase62Encoding:
    """Test base62 encoding/decoding functions."""

    def test_encode_base62_zero(self):
        """Test encoding zero."""
        assert encode_base62(0) == "0"

    def test_encode_base62_positive_numbers(self):
        """Test encoding positive numbers."""
        assert encode_base62(1) == "1"
        assert encode_base62(61) == "z"
        assert encode_base62(62) == "10"
        assert encode_base62(123456) == "w7e"

    def test_decode_base62_zero(self):
        """Test decoding zero."""
        assert decode_base62("0") == 0

    def test_decode_base62_positive_numbers(self):
        """Test decoding positive numbers."""
        assert decode_base62("1") == 1
        assert decode_base62("z") == 61
        assert decode_base62("10") == 62
        assert decode_base62("w7e") == 123456

    def test_encode_decode_roundtrip(self):
        """Test that encoding and decoding are inverse operations."""
        test_numbers = [0, 1, 61, 62, 123, 456, 789, 123456, 999999]
        for num in test_numbers:
            encoded = encode_base62(num)
            decoded = decode_base62(encoded)
            assert decoded == num


class TestURLValidation:
    """Test URL validation and normalization functions."""

    def test_is_valid_url_valid_urls(self):
        """Test valid URLs."""
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://www.example.com/path",
            "http://subdomain.example.com:8080/path?query=value",
        ]
        for url in valid_urls:
            assert is_valid_url(url)

    def test_is_valid_url_invalid_urls(self):
        """Test invalid URLs."""
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com",  # Wrong scheme
            "//example.com",  # Missing scheme
            "https://",  # Missing netloc
            None,
        ]
        for url in invalid_urls:
            assert not is_valid_url(url)

    def test_normalize_url_with_scheme(self):
        """Test normalizing URLs that already have a scheme."""
        assert normalize_url("https://example.com") == "https://example.com"
        assert normalize_url("http://example.com") == "http://example.com"

    def test_normalize_url_without_scheme(self):
        """Test normalizing URLs without a scheme."""
        assert normalize_url("example.com") == "https://example.com"
        assert normalize_url("www.example.com") == "https://www.example.com"

    def test_extract_domain_valid_urls(self):
        """Test extracting domain from valid URLs."""
        test_cases = [
            ("https://example.com", "example.com"),
            ("http://www.example.com", "www.example.com"),
            ("https://subdomain.example.com:8080/path", "subdomain.example.com:8080"),
        ]
        for url, expected_domain in test_cases:
            assert extract_domain(url) == expected_domain

    def test_extract_domain_invalid_urls(self):
        """Test extracting domain from invalid URLs."""
        invalid_urls = ["", "not-a-url", None]
        for url in invalid_urls:
            assert extract_domain(url) is None


class TestShortCodeValidation:
    """Test short code validation functions."""

    def test_is_valid_short_code_valid_codes(self):
        """Test valid short codes."""
        valid_codes = ["abc123", "ABC", "123", "a1B2c3"]
        for code in valid_codes:
            assert is_valid_short_code(code)

    def test_is_valid_short_code_invalid_codes(self):
        """Test invalid short codes."""
        invalid_codes = [
            "",  # Empty
            None,  # None
            "abc-123",  # Contains hyphen
            "abc_123",  # Contains underscore
            "abc 123",  # Contains space
            "a" * 11,  # Too long
        ]
        for code in invalid_codes:
            assert not is_valid_short_code(code)

    def test_validate_custom_code_valid(self):
        """Test validating valid custom codes."""
        valid, message = validate_custom_code("abc123")
        assert valid
        assert message == "Valid"

    def test_validate_custom_code_too_short(self):
        """Test validating too short custom codes."""
        valid, message = validate_custom_code("ab")
        assert not valid
        assert "at least 3 characters" in message

    def test_validate_custom_code_too_long(self):
        """Test validating too long custom codes."""
        valid, message = validate_custom_code("a" * 11)
        assert not valid
        assert "at most 10 characters" in message

    def test_validate_custom_code_reserved_words(self):
        """Test validating reserved words."""
        reserved_words = ["api", "admin", "www", "app"]
        for word in reserved_words:
            valid, message = validate_custom_code(word)
            assert not valid
            assert "reserved" in message


class TestIPHashing:
    """Test IP address hashing functions."""

    def test_hash_ip_address_consistency(self):
        """Test that hashing the same IP produces the same result."""
        ip = "192.168.1.1"
        hash1 = hash_ip_address(ip)
        hash2 = hash_ip_address(ip)
        assert hash1 == hash2

    def test_hash_ip_address_with_salt(self):
        """Test hashing IP with salt."""
        ip = "192.168.1.1"
        hash_no_salt = hash_ip_address(ip)
        hash_with_salt = hash_ip_address(ip, "salt")
        assert hash_no_salt != hash_with_salt

    def test_hash_ip_address_length(self):
        """Test that hashed IP has expected length."""
        ip = "192.168.1.1"
        hashed = hash_ip_address(ip)
        assert len(hashed) == 16


class TestUserAgentParsing:
    """Test user agent parsing functions."""

    def test_parse_user_agent_info_chrome(self):
        """Test parsing Chrome user agent."""
        ua_string = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        info = parse_user_agent_info(ua_string)
        
        assert "Chrome" in info["browser"]
        assert "Windows" in info["os"]
        assert not info["is_mobile"]
        assert not info["is_bot"]

    def test_parse_user_agent_info_mobile(self):
        """Test parsing mobile user agent."""
        ua_string = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1"
        info = parse_user_agent_info(ua_string)
        
        assert info["is_mobile"]
        assert "iPhone" in info["os"] or "iOS" in info["os"]

    def test_parse_user_agent_info_invalid(self):
        """Test parsing invalid user agent."""
        info = parse_user_agent_info("")
        
        assert info["browser"] == "Unknown"
        assert info["os"] == "Unknown"
        assert info["device_type"] == "Unknown"


class TestClientIP:
    """Test client IP extraction functions."""

    def test_get_client_ip_x_forwarded_for(self):
        """Test getting client IP from X-Forwarded-For header."""
        mock_request = Mock()
        mock_request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_x_real_ip(self):
        """Test getting client IP from X-Real-IP header."""
        mock_request = Mock()
        mock_request.headers = {"X-Real-IP": "192.168.1.1"}
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_client_host(self):
        """Test getting client IP from request.client.host."""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.1"
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_no_ip(self):
        """Test when no IP is available."""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.client = None
        
        ip = get_client_ip(mock_request)
        assert ip is None


class TestSafeRedirectURL:
    """Test safe redirect URL validation."""

    def test_is_safe_redirect_url_valid(self):
        """Test valid redirect URLs."""
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://subdomain.example.com/path",
        ]
        for url in valid_urls:
            assert is_safe_redirect_url(url)

    def test_is_safe_redirect_url_invalid_scheme(self):
        """Test invalid schemes."""
        invalid_urls = [
            "ftp://example.com",
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
        ]
        for url in invalid_urls:
            assert not is_safe_redirect_url(url)

    def test_is_safe_redirect_url_with_allowed_domains(self):
        """Test with allowed domains list."""
        allowed_domains = ["example.com", "trusted.com"]
        
        assert is_safe_redirect_url("https://example.com", allowed_domains)
        assert is_safe_redirect_url("https://sub.example.com", allowed_domains)
        assert not is_safe_redirect_url("https://malicious.com", allowed_domains)


class TestMetadataSanitization:
    """Test metadata sanitization functions."""

    def test_sanitize_metadata_valid(self):
        """Test sanitizing valid metadata."""
        metadata = {"key": "value", "number": 123}
        result = sanitize_metadata(metadata)
        assert result == metadata

    def test_sanitize_metadata_too_large(self):
        """Test sanitizing metadata that's too large."""
        large_metadata = {"key": "x" * 1000}
        result = sanitize_metadata(large_metadata, max_size=100)
        assert "error" in result
        assert result["error"] == "metadata_too_large"

    def test_sanitize_metadata_invalid_type(self):
        """Test sanitizing invalid metadata type."""
        result = sanitize_metadata("not a dict")
        assert result == {}

    def test_sanitize_metadata_non_serializable(self):
        """Test sanitizing non-serializable metadata."""
        class NonSerializable:
            pass
        
        # This should handle the non-serializable object gracefully
        metadata = {"obj": NonSerializable()}
        result = sanitize_metadata(metadata)
        # The function should either serialize it as string or return error
        assert isinstance(result, dict)


class TestURLCreation:
    """Test URL creation functions."""

    def test_create_short_url(self):
        """Test creating short URL."""
        base_url = "https://short.ly"
        short_code = "abc123"
        expected = "https://short.ly/abc123"
        
        result = create_short_url(base_url, short_code)
        assert result == expected

    def test_create_short_url_trailing_slash(self):
        """Test creating short URL with trailing slash in base URL."""
        base_url = "https://short.ly/"
        short_code = "abc123"
        expected = "https://short.ly/abc123"
        
        result = create_short_url(base_url, short_code)
        assert result == expected
