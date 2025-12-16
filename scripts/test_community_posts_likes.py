#!/usr/bin/env python3
"""
Test Script: Community Posts Like System
Tests the new like functionality for community posts
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
API_BASE_URL = "http://localhost:5070"
SECRET_KEY = os.getenv("API_SECRET_KEY", "dev-secret-key-change-in-production")

print(f"🔑 Using SECRET_KEY: {SECRET_KEY[:20]}...")


def create_test_token(role="admin", username="TestUser", discord_id="123456789"):
    """Create a test JWT token"""
    token_data = {
        "user": username,
        "discord_id": discord_id,
        "role": role,
        "role_name": "Admin",
        "permissions": ["all"],
        "auth_type": "test",
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(token_data, SECRET_KEY, algorithm="HS256")


def test_api_health():
    """Test if API is responding"""
    print("\n" + "=" * 60)
    print("🏥 Testing API Health")
    print("=" * 60)

    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=5)
        print(f"✅ API is reachable (Status: {response.status_code})")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ API is not reachable: {e}")
        return False


def test_create_post(token):
    """Create a test post"""
    print("\n" + "=" * 60)
    print("📝 Creating Test Post")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"content": "Test post for like functionality 🎉"}

    response = requests.post(f"{API_BASE_URL}/api/posts", headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        result = response.json()
        post_id = result.get("post_id")
        print(f"✅ Post created: ID {post_id}")
        return post_id
    else:
        print(f"❌ Failed: {response.text}")
        return None


def test_like_post(token, post_id, user_name="User1"):
    """Test liking a post"""
    print(f"\n👍 Testing LIKE POST (User: {user_name})")
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    response = requests.post(
        f"{API_BASE_URL}/api/community_posts/{post_id}/like",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Success!")
        print(f"   Action: {result.get('action')}")
        print(f"   Like Count: {result.get('like_count')}")
        print(f"   Has Liked: {result.get('has_liked')}")
        print(f"   XP Awarded: {result.get('xp_awarded')}")
        return result
    else:
        print(f"❌ Failed: {response.text}")
        return None


def test_get_likes(token, post_id):
    """Test getting like count"""
    print(f"\n📊 Testing GET LIKES")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{API_BASE_URL}/api/community_posts/{post_id}/likes",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Success!")
        print(f"   Like Count: {result.get('like_count')}")
        print(f"   Has Liked: {result.get('has_liked')}")
        return result
    else:
        print(f"❌ Failed: {response.text}")
        return None


def test_unlike_post(token, post_id):
    """Test unliking a post"""
    print(f"\n👎 Testing UNLIKE POST")
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    response = requests.post(
        f"{API_BASE_URL}/api/community_posts/{post_id}/like",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Success!")
        print(f"   Action: {result.get('action')}")
        print(f"   Like Count: {result.get('like_count')}")
        print(f"   Has Liked: {result.get('has_liked')}")
        return result
    else:
        print(f"❌ Failed: {response.text}")
        return None


def test_self_like_prevention(token_author, post_id):
    """Test that self-liking is prevented"""
    print(f"\n🚫 Testing SELF-LIKE PREVENTION")
    
    headers = {"Authorization": f"Bearer {token_author}", "Content-Type": "application/json"}
    
    response = requests.post(
        f"{API_BASE_URL}/api/community_posts/{post_id}/like",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 400:
        print(f"✅ Self-like correctly prevented!")
        print(f"   Error: {response.json().get('error')}")
        return True
    else:
        print(f"❌ Self-like was NOT prevented! Status: {response.status_code}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🧪 COMMUNITY POSTS LIKE SYSTEM TEST")
    print("=" * 60)

    # Test API health
    if not test_api_health():
        print("\n❌ API is not running. Start it with: python start_with_api.py")
        return

    # Create tokens for two different users
    token_user1 = create_test_token(username="TestUser1", discord_id="111111111")
    token_user2 = create_test_token(username="TestUser2", discord_id="222222222")

    # Create a test post (User1 creates it)
    post_id = test_create_post(token_user1)
    if not post_id:
        print("\n❌ Failed to create test post")
        return

    # Test 1: User2 likes the post
    result = test_like_post(token_user2, post_id, "User2")
    if not result:
        print("\n❌ Test failed")
        return
    
    # Verify like count is 1
    if result.get("like_count") != 1:
        print(f"\n❌ Expected like_count=1, got {result.get('like_count')}")
        return

    # Test 2: Get likes
    result = test_get_likes(token_user2, post_id)
    if not result or result.get("like_count") != 1:
        print("\n❌ Get likes failed")
        return

    # Test 3: User2 unlikes the post
    result = test_unlike_post(token_user2, post_id)
    if not result or result.get("like_count") != 0:
        print(f"\n❌ Unlike failed - like_count should be 0, got {result.get('like_count')}")
        return

    # Test 4: User2 likes again
    result = test_like_post(token_user2, post_id, "User2 (again)")
    if not result or result.get("like_count") != 1:
        print("\n❌ Second like failed")
        return

    # Test 5: Self-like prevention
    if not test_self_like_prevention(token_user1, post_id):
        print("\n❌ Self-like prevention test failed")
        return

    # Test 6: Multiple users like
    print("\n" + "=" * 60)
    print("👥 Testing Multiple Users Liking")
    print("=" * 60)
    
    token_user3 = create_test_token(username="TestUser3", discord_id="333333333")
    result = test_like_post(token_user3, post_id, "User3")
    
    if not result or result.get("like_count") != 2:
        print(f"\n❌ Multiple likes failed - expected 2, got {result.get('like_count')}")
        return

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nTest Summary:")
    print("  ✅ Post creation")
    print("  ✅ Like post")
    print("  ✅ Get likes")
    print("  ✅ Unlike post")
    print("  ✅ Re-like post")
    print("  ✅ Self-like prevention")
    print("  ✅ Multiple users liking")


if __name__ == "__main__":
    main()
