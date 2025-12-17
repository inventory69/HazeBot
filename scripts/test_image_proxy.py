#!/usr/bin/env python3
"""
Test the new Image Proxy feature for Community Posts

Tests:
1. Get post images with different sizes (thumbnail, fullscreen)
2. Test compression quality settings
3. Verify cache headers
4. Test original bypass
"""

import os
import sys
import requests
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

API_BASE_URL = "http://localhost:5070"
SECRET_KEY = os.getenv("API_SECRET_KEY", "dev-secret-key-change-in-production")


def create_test_token():
    """Create a test JWT token"""
    token_data = {
        "user": "TestUser",
        "discord_id": "441228238091026433",
        "role": "admin",
        "role_name": "Admin",
        "permissions": ["all"],
        "auth_type": "test",
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(token_data, SECRET_KEY, algorithm="HS256")


def test_image_proxy():
    """Test the image proxy endpoint"""
    print("\n" + "=" * 80)
    print("🖼️  Testing Community Posts Image Proxy")
    print("=" * 80 + "\n")

    token = create_test_token()
    headers = {"Authorization": f"Bearer {token}"}

    # First, get list of posts with images
    print("📋 Fetching community posts...")
    response = requests.get(f"{API_BASE_URL}/api/posts?limit=50", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch posts: {response.status_code}")
        return
    
    posts = response.json().get("posts", [])
    posts_with_images = [p for p in posts if p.get("image_url")]
    
    if not posts_with_images:
        print("⚠️  No posts with images found. Cannot test proxy.")
        print("   Please create a post with an image first.")
        return
    
    print(f"✅ Found {len(posts_with_images)} posts with images\n")
    
    # Test with first post that has an image
    test_post = posts_with_images[0]
    post_id = test_post["id"]
    
    print(f"🔍 Testing with Post #{post_id}")
    print(f"   Original URL: {test_post['image_url'][:80]}...\n")
    
    # Test cases
    test_cases = [
        {
            "name": "Thumbnail (800px, 80% quality)",
            "params": {"width": 800, "quality": 80},
            "expected_size": "~150-300 KB"
        },
        {
            "name": "Small (400px, 60% quality)",
            "params": {"width": 400, "quality": 60},
            "expected_size": "~50-100 KB"
        },
        {
            "name": "Fullscreen (1920px, 95% quality)",
            "params": {"width": 1920, "quality": 95},
            "expected_size": "~800 KB - 1.5 MB"
        },
        {
            "name": "WebP format (800px, 80% quality)",
            "params": {"width": 800, "quality": 80, "format": "webp"},
            "expected_size": "~100-200 KB"
        },
        {
            "name": "Original (bypass proxy)",
            "params": {"original": "true"},
            "expected_size": "~2 MB (redirect)"
        },
    ]
    
    for test_case in test_cases:
        print(f"📸 {test_case['name']}")
        print(f"   Expected: {test_case['expected_size']}")
        
        url = f"{API_BASE_URL}/api/community_posts/images/{post_id}"
        
        try:
            response = requests.get(url, params=test_case["params"], allow_redirects=False, timeout=15)
            
            if response.status_code == 302:
                # Redirect to original
                print(f"   Status: 302 REDIRECT ✅")
                print(f"   Location: {response.headers.get('Location', 'N/A')[:80]}...")
            elif response.status_code == 200:
                # Got image
                size_bytes = len(response.content)
                size_kb = size_bytes / 1024
                size_mb = size_kb / 1024
                
                if size_mb >= 1:
                    size_str = f"{size_mb:.2f} MB"
                else:
                    size_str = f"{size_kb:.0f} KB"
                
                content_type = response.headers.get("Content-Type", "unknown")
                cache_control = response.headers.get("Cache-Control", "none")
                etag = response.headers.get("ETag", "none")
                
                print(f"   Status: 200 OK ✅")
                print(f"   Size: {size_str} ({size_bytes:,} bytes)")
                print(f"   Type: {content_type}")
                print(f"   Cache: {cache_control}")
                print(f"   ETag: {etag}")
                
                # Check if X-Original-URL header exists
                original_url = response.headers.get("X-Original-URL")
                if original_url:
                    print(f"   X-Original-URL: {original_url[:60]}...")
            else:
                print(f"   Status: {response.status_code} ❌")
                if response.headers.get("Content-Type") == "application/json":
                    error = response.json().get("error", "Unknown error")
                    print(f"   Error: {error}")
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()
    
    print("=" * 80)
    print("✅ Image Proxy Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    test_image_proxy()
