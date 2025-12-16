#!/usr/bin/env python3
"""
Test Script: Community Posts API
Tests all CRUD operations for the new Community Posts feature
"""

import base64
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
API_BASE_URL = "http://localhost:5070"
SECRET_KEY = os.getenv("API_SECRET_KEY", "dev-secret-key-change-in-production")

if not SECRET_KEY:
    print("❌ ERROR: API_SECRET_KEY not found in .env file!")
    sys.exit(1)

print(f"🔑 Using SECRET_KEY: {SECRET_KEY[:20]}...")


def create_test_token(role="admin", username="TestUser", discord_id="123456789"):
    """Create a test JWT token with proper structure"""
    token_data = {
        "user": username,
        "discord_id": discord_id,
        "role": role,
        "role_name": "Admin" if role == "admin" else "Moderator" if role == "mod" else "Lootling",
        "permissions": ["all"],
        "auth_type": "test",
        "exp": datetime.utcnow() + timedelta(hours=24),
    }

    token = jwt.encode(token_data, SECRET_KEY, algorithm="HS256")
    return token


def test_api_health():
    """Test if API is responding"""
    print("\n" + "=" * 60)
    print("🏥 Testing API Health")
    print("=" * 60)

    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=5)
        # API is reachable even if health check has issues
        print(f"✅ API is reachable (Status: {response.status_code})")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ API is not reachable: {e}")
        return False


def test_create_post(token, content=None, image=None, is_announcement=False):
    """Test POST /api/posts - Create a post"""
    print("\n" + "=" * 60)
    print("📝 Testing CREATE POST")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    data = {"content": content, "image": image, "is_announcement": is_announcement}

    print("Request: POST /api/posts")
    print(f"Data: content={'✓' if content else '✗'}, image={'✓' if image else '✗'}, announcement={is_announcement}")

    try:
        response = requests.post(f"{API_BASE_URL}/api/posts", headers=headers, json=data)
        print(f"Status: {response.status_code}")

        if response.status_code in [200, 201]:
            result = response.json()
            print("✅ Post created successfully!")
            print(f"   Post ID: {result.get('post_id')}")
            print(f"   Created at: {result.get('created_at')}")
            if result.get("discord_message_id"):
                print(f"   Discord Message ID: {result.get('discord_message_id')}")
            return result.get("post_id")
        else:
            print(f"❌ Failed: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None


def test_get_posts(token, limit=10, offset=0):
    """Test GET /api/posts - Get all posts"""
    print("\n" + "=" * 60)
    print("📖 Testing GET POSTS")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {token}"}

    params = {"limit": limit, "offset": offset}

    print(f"Request: GET /api/posts?limit={limit}&offset={offset}")

    try:
        response = requests.get(f"{API_BASE_URL}/api/posts", headers=headers, params=params)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            posts = result.get("posts", [])
            total = result.get("total", 0)
            print(f"✅ Retrieved {len(posts)} posts (Total: {total})")

            for post in posts[:3]:  # Show first 3 posts
                print(f"   - Post #{post.get('id')}: {post.get('content', 'No content')[:50]}...")

            return posts
        else:
            print(f"❌ Failed: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None


def test_update_post(token, post_id, new_content):
    """Test PUT /api/posts/:id - Update a post"""
    print("\n" + "=" * 60)
    print(f"✏️  Testing UPDATE POST #{post_id}")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    data = {"content": new_content}

    print(f"Request: PUT /api/posts/{post_id}")
    print(f"New content: {new_content}")

    try:
        response = requests.put(f"{API_BASE_URL}/api/posts/{post_id}", headers=headers, json=data)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ Post updated successfully!")
            print(f"   Edited at: {result.get('edited_at')}")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False


def test_delete_post(token, post_id):
    """Test DELETE /api/posts/:id - Delete a post"""
    print("\n" + "=" * 60)
    print(f"🗑️  Testing DELETE POST #{post_id}")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {token}"}

    print(f"Request: DELETE /api/posts/{post_id}")

    try:
        response = requests.delete(f"{API_BASE_URL}/api/posts/{post_id}", headers=headers)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ Post deleted successfully!")
            print(f"   Deleted at: {result.get('deleted_at')}")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False


def create_test_image():
    """Create a small test image in base64 format"""
    # 1x1 red pixel PNG
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(png_bytes).decode("utf-8")


def main():
    """Run all tests"""
    print("\n" + "🔧" * 30)
    print("🚀 COMMUNITY POSTS API TEST SUITE")
    print("🔧" * 30)

    # Step 1: Check API health
    if not test_api_health():
        print("\n❌ API is not available. Make sure the bot is running.")
        return

    # Step 2: Create test token
    print("\n" + "=" * 60)
    print("🎫 Creating Test Token")
    print("=" * 60)
    token = create_test_token(role="admin", username="TestAdmin", discord_id="987654321")
    print(f"✅ Token created: {token[:30]}...")

    # Step 3: Test CREATE - Text only
    post_id_1 = test_create_post(token, content="🧪 Test Post #1 - Text only content", is_announcement=False)

    # Step 4: Test CREATE - Text + Image
    test_image = create_test_image()
    post_id_2 = test_create_post(token, content="🧪 Test Post #2 - With image", image=test_image, is_announcement=False)

    # Step 5: Test CREATE - Announcement (admin only)
    _post_id_3 = test_create_post(token, content="📢 Test Announcement - Admin only", is_announcement=True)

    # Step 6: Test GET - Retrieve all posts
    _posts = test_get_posts(token, limit=10, offset=0)

    # Step 7: Test UPDATE - Modify first post
    if post_id_1:
        test_update_post(token, post_id_1, "✏️ Updated content for test post #1")

    # Step 8: Test DELETE - Remove second post
    if post_id_2:
        test_delete_post(token, post_id_2)

    # Step 9: Test GET again to verify changes
    print("\n" + "=" * 60)
    print("🔄 Verifying Changes")
    print("=" * 60)
    test_get_posts(token, limit=10, offset=0)

    # Summary
    print("\n" + "🎉" * 30)
    print("✅ TEST SUITE COMPLETED")
    print("🎉" * 30)
    print("\nCheck the following:")
    print("1. TestData/community_posts.db should exist")
    print("2. TestData/community_posts_images/ should contain uploaded images")
    print("3. Discord channel should have test posts (if bot is connected)")
    print("4. Check terminal output above for any errors")


if __name__ == "__main__":
    main()
