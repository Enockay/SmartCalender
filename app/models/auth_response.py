from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AuthResponse:
    """Authentication response model from external API."""
    
    # User identification
    user_id: str
    email: str
    name: str
    
    # Authentication tokens
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    
    # Subscription information
    subscription_tier: str = "free"  # free, basic, premium, enterprise
    subscription_status: str = "active"  # active, cancelled, expired, trial
    subscription_expires_at: Optional[datetime] = None
    subscription_features: list[str] = None  # List of enabled features
    
    # User preferences/metadata
    timezone: Optional[str] = None
    language: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Additional metadata
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    role: Optional[str] = None  # user, admin, manager
    
    # API response metadata
    api_version: Optional[str] = None
    server_timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.subscription_features is None:
            self.subscription_features = []
