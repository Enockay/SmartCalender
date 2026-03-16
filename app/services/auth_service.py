from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.logger import get_logger
from app.models.auth_response import AuthResponse
from app.services.settings_service import SettingsService


logger = get_logger(__name__)


class AuthService:
    """Service for handling authentication with external API."""
    
    # API Configuration - should be configurable via AppConfig
    DEFAULT_API_BASE_URL = "https://api.smartcalender.com/v1"
    LOGIN_ENDPOINT = "/auth/login"
    
    def __init__(self, settings_service: Optional[SettingsService] = None):
        self._settings = settings_service or SettingsService()
        self._api_base_url = self._get_api_base_url()
        self._session = self._create_session()
    
    def _get_api_base_url(self) -> str:
        """Get API base URL from settings or use default."""
        # Could be stored in settings: self._settings.get("api_base_url", self.DEFAULT_API_BASE_URL)
        return self.DEFAULT_API_BASE_URL
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def login(self, email: str, password: str, remember_me: bool = False) -> AuthResponse:
        """
        Authenticate user with external API.
        
        Args:
            email: User email address
            password: User password
            remember_me: Whether to remember the login
            
        Returns:
            AuthResponse object with user data and tokens
            
        Raises:
            requests.RequestException: If API request fails
            ValueError: If authentication fails or response is invalid
        """
        # ── Local dummy login (no network) ───────────────────────────────────
        # This allows development and UI testing without a real API.
        # Credentials:
        #   email:    enock@example.com
        #   password: test123
        if email.lower() == "enock@example.com" and password == "test123":
            now = datetime.now(timezone.utc)
            one_month_later = now + timedelta(days=30)
            
            dummy_payload = {
                # Core identity
                "user_id": "dummy_enock_001",
                "email": email,
                "name": "Enock",
                # Tokens
                "access_token": "dummy-access-token",
                "refresh_token": "dummy-refresh-token",
                "token_expires_at": one_month_later.isoformat().replace("+00:00", "Z"),
                # Subscription details
                "subscription": {
                    "tier": "premium",              # matches Settings / Account badge
                    "status": "active",
                    "expires_at": one_month_later.isoformat().replace("+00:00", "Z"),
                    "features": [
                        "1_month_trial",
                        "price_1_usd",
                        "calendar_sync",
                        "priority_notifications",
                        "daily_summary_email",
                        "advanced_reminders",
                    ],
                    # Extra info for future UI use (ignored safely by current parser)
                    "currency": "USD",
                    "amount": 1.00,
                    "billing_period": "monthly",
                },
                # Top-level field so subscription_expires_at gets parsed correctly
                "subscription_expires_at": one_month_later.isoformat().replace("+00:00", "Z"),
                # Profile / preferences
                "timezone": "America/New_York",
                "language": "en",
                "avatar_url": "https://example.com/avatars/enock.png",
                "organization": {
                    "id": "org_dummy_1",
                    "name": "Smart Calender Test Org",
                    "role": "Owner",
                    "team_size": 3,
                },
                "role": "user",
                # Metadata
                "api_version": "v1",
                "server_timestamp": now.isoformat().replace("+00:00", "Z"),
            }
            
            logger.info("Using local dummy login for Enock.")
            return self._parse_response(dummy_payload)
        
        url = urljoin(self._api_base_url, self.LOGIN_ENDPOINT)
        
        payload = {
            "email": email,
            "password": password,
            "remember_me": remember_me,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        try:
            logger.info(f"Attempting login for user: {email}")
            response = self._session.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            auth_response = self._parse_response(data)
            
            logger.info(f"Login successful for user: {email}")
            return auth_response
            
        except requests.exceptions.Timeout:
            logger.error("Login request timed out")
            raise ValueError("Connection timeout. Please check your internet connection.")
        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to authentication server")
            raise ValueError("Cannot connect to server. Please check your internet connection.")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.warning(f"Authentication failed for user: {email}")
                raise ValueError("Invalid email or password. Please try again.")
            elif e.response.status_code == 403:
                raise ValueError("Account is disabled. Please contact support.")
            else:
                logger.error(f"HTTP error during login: {e.response.status_code}")
                raise ValueError(f"Server error ({e.response.status_code}). Please try again later.")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from server")
            raise ValueError("Invalid response from server. Please try again.")
        except Exception as e:
            logger.error(f"Unexpected error during login: {e}", exc_info=True)
            raise ValueError("An unexpected error occurred. Please try again.")
    
    def _parse_response(self, data: dict) -> AuthResponse:
        """Parse API response into AuthResponse model."""
        try:
            # Parse token expiration if provided
            token_expires_at = None
            if "token_expires_at" in data:
                token_expires_at = datetime.fromisoformat(data["token_expires_at"].replace("Z", "+00:00"))
            
            # Parse subscription expiration if provided
            subscription_expires_at = None
            if "subscription_expires_at" in data:
                subscription_expires_at = datetime.fromisoformat(data["subscription_expires_at"].replace("Z", "+00:00"))
            
            # Parse server timestamp if provided
            server_timestamp = None
            if "server_timestamp" in data:
                server_timestamp = datetime.fromisoformat(data["server_timestamp"].replace("Z", "+00:00"))
            
            return AuthResponse(
                user_id=str(data.get("user_id", "")),
                email=data.get("email", ""),
                name=data.get("name", ""),
                access_token=data.get("access_token", ""),
                refresh_token=data.get("refresh_token"),
                token_expires_at=token_expires_at,
                subscription_tier=data.get("subscription", {}).get("tier", "free"),
                subscription_status=data.get("subscription", {}).get("status", "active"),
                subscription_expires_at=subscription_expires_at,
                subscription_features=data.get("subscription", {}).get("features", []),
                timezone=data.get("timezone"),
                language=data.get("language"),
                avatar_url=data.get("avatar_url"),
                organization_id=data.get("organization", {}).get("id"),
                organization_name=data.get("organization", {}).get("name"),
                role=data.get("role"),
                api_version=data.get("api_version"),
                server_timestamp=server_timestamp,
            )
        except KeyError as e:
            logger.error(f"Missing required field in API response: {e}")
            raise ValueError("Invalid response format from server.")
        except Exception as e:
            logger.error(f"Error parsing API response: {e}", exc_info=True)
            raise ValueError("Failed to parse server response.")
    
    def check_server_status(self) -> bool:
        """
        Check if the authentication server is reachable.
        
        Returns:
            True if server is reachable, False otherwise
        """
        try:
            # Try to ping a health/status endpoint if available
            url = urljoin(self._api_base_url, "/health")
            response = self._session.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
