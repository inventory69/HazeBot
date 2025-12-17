#!/usr/bin/env python3
"""
Debug: List all registered Flask routes
"""

import os
import sys
from datetime import datetime, timedelta

import jwt
import requests
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = "http://192.168.0.188:5070"
SECRET_KEY = os.getenv("API_SECRET_KEY", "dev-secret-key-change-in-production")


def create_test_token():
    """Create a test JWT token"""
    token_data = {
        "user": "DebugUser",
        "discord_id": "123456789",
        "role": "admin",
        "role_name": "Admin",
        "permissions": ["all"],
        "auth_type": "test",
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(token_data, SECRET_KEY, algorithm="HS256")


def test_endpoint(method, path, token):
    """Test if endpoint exists"""
    headers = {"Authorization": f"Bearer {token}"}

    try:
        if method == "GET":
            response = requests.get(f"{API_BASE_URL}{path}", headers=headers, timeout=2)
        elif method == "POST":
            response = requests.post(f"{API_BASE_URL}{path}", headers=headers, timeout=2)

        return response.status_code
    except Exception as e:
        return str(e)


def main():
    print("\n" + "=" * 60)
    print("🔍 Testing Community Posts Endpoints")
    print("=" * 60)

    token = create_test_token()

    endpoints = [
        ("GET", "/api/posts", "Get posts"),
        ("POST", "/api/posts", "Create post"),
        ("POST", "/api/community_posts/17/like", "Toggle like (full path)"),
        ("GET", "/api/community_posts/17/likes", "Get likes (full path)"),
        ("POST", "/api/posts/17/like", "Toggle like (short path)"),
        ("GET", "/api/posts/17/likes", "Get likes (short path)"),
    ]

    for method, path, description in endpoints:
        status = test_endpoint(method, path, token)
        emoji = "✅" if isinstance(status, int) and status < 500 else "❌"
        print(f"{emoji} {method:5s} {path:40s} -> {status:4} ({description})")


if __name__ == "__main__":
    main()
