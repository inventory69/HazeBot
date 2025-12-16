#!/usr/bin/env python3
"""
Race Condition Test: Community Posts Like System
Tests concurrent like operations to detect potential data loss
"""

import os
import sys
from datetime import datetime, timedelta
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def create_test_post(token):
    """Create a test post"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"content": f"Race condition test post - {datetime.now().isoformat()}"}

    response = requests.post(f"{API_BASE_URL}/api/posts", headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        result = response.json()
        return result.get("post_id")
    return None


def like_post(post_id, user_id, user_name):
    """Like a post (returns success status, like_count, action)"""
    token = create_test_token(username=user_name, discord_id=str(user_id))
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/community_posts/{post_id}/like",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            return True, result.get('like_count'), result.get('action'), user_id
        else:
            return False, 0, 'error', user_id
    except Exception as e:
        print(f"❌ Error for user {user_id}: {e}")
        return False, 0, 'exception', user_id


def get_final_like_count(post_id, token):
    """Get the final like count"""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{API_BASE_URL}/api/community_posts/{post_id}/likes",
        headers=headers
    )
    
    if response.status_code == 200:
        return response.json().get('like_count', 0)
    return -1


def test_concurrent_likes(num_users=10):
    """Test concurrent likes from multiple users"""
    print("\n" + "=" * 60)
    print(f"🔄 Testing {num_users} Concurrent Likes")
    print("=" * 60)
    
    # Create test post
    creator_token = create_test_token(username="Creator", discord_id="999999999")
    post_id = create_test_post(creator_token)
    
    if not post_id:
        print("❌ Failed to create test post")
        return False
    
    print(f"✅ Created test post: ID {post_id}")
    print(f"📤 Sending {num_users} concurrent like requests...")
    
    # Create unique users
    user_ids = [1000000 + i for i in range(num_users)]
    
    # Start timer
    start_time = time.time()
    
    # Execute concurrent likes
    results = []
    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = [
            executor.submit(like_post, post_id, user_id, f"User{user_id}")
            for user_id in user_ids
        ]
        
        for future in as_completed(futures):
            results.append(future.result())
    
    elapsed = time.time() - start_time
    
    # Analyze results
    successful = sum(1 for success, _, _, _ in results if success)
    failed = len(results) - successful
    
    print(f"\n📊 Results after {elapsed:.2f}s:")
    print(f"   ✅ Successful: {successful}/{num_users}")
    print(f"   ❌ Failed: {failed}/{num_users}")
    
    # Wait a bit for file writes to complete
    time.sleep(1)
    
    # Check final like count
    final_count = get_final_like_count(post_id, creator_token)
    print(f"\n🎯 Expected Like Count: {num_users}")
    print(f"📈 Actual Like Count: {final_count}")
    
    # Check for race condition
    if final_count == num_users:
        print("✅ NO RACE CONDITION - All likes saved correctly!")
        return True
    else:
        lost_likes = num_users - final_count
        print(f"❌ RACE CONDITION DETECTED - Lost {lost_likes} likes!")
        print(f"   Data Loss: {(lost_likes / num_users) * 100:.1f}%")
        return False


def test_concurrent_like_unlike(num_operations=20):
    """Test concurrent like/unlike operations (toggle spam)"""
    print("\n" + "=" * 60)
    print(f"🔄 Testing {num_operations} Concurrent Like/Unlike Operations")
    print("=" * 60)
    
    # Create test post
    creator_token = create_test_token(username="Creator", discord_id="888888888")
    post_id = create_test_post(creator_token)
    
    if not post_id:
        print("❌ Failed to create test post")
        return False
    
    print(f"✅ Created test post: ID {post_id}")
    
    # Use same user for all operations (toggle test)
    user_id = 1234567
    
    print(f"📤 Sending {num_operations} rapid like/unlike toggles from same user...")
    
    start_time = time.time()
    
    # Execute rapid toggles
    results = []
    with ThreadPoolExecutor(max_workers=num_operations) as executor:
        futures = [
            executor.submit(like_post, post_id, user_id, f"User{user_id}")
            for _ in range(num_operations)
        ]
        
        for future in as_completed(futures):
            results.append(future.result())
    
    elapsed = time.time() - start_time
    
    # Count actions
    added = sum(1 for _, _, action, _ in results if action == 'added')
    removed = sum(1 for _, _, action, _ in results if action == 'removed')
    
    print(f"\n📊 Results after {elapsed:.2f}s:")
    print(f"   ➕ Added: {added}")
    print(f"   ➖ Removed: {removed}")
    
    # Wait for file writes
    time.sleep(1)
    
    # Check final state
    final_count = get_final_like_count(post_id, creator_token)
    
    print(f"\n🎯 Final Like Count: {final_count}")
    
    # Final state should be deterministic based on operation count
    expected_state = num_operations % 2  # 0 if even, 1 if odd
    
    if final_count == expected_state:
        print(f"✅ Consistent State - Expected {expected_state}, got {final_count}")
        return True
    else:
        print(f"❌ Inconsistent State - Expected {expected_state}, got {final_count}")
        return False


def test_stress(num_posts=5, likes_per_post=10):
    """Stress test: Multiple posts with concurrent likes"""
    print("\n" + "=" * 60)
    print(f"💪 Stress Test: {num_posts} posts × {likes_per_post} concurrent likes")
    print("=" * 60)
    
    creator_token = create_test_token(username="Creator", discord_id="777777777")
    
    all_passed = True
    
    for post_num in range(num_posts):
        print(f"\n📝 Post {post_num + 1}/{num_posts}:")
        
        # Create post
        post_id = create_test_post(creator_token)
        if not post_id:
            print("   ❌ Failed to create post")
            all_passed = False
            continue
        
        # Create users
        user_ids = [2000000 + post_num * 100 + i for i in range(likes_per_post)]
        
        # Concurrent likes
        results = []
        with ThreadPoolExecutor(max_workers=likes_per_post) as executor:
            futures = [
                executor.submit(like_post, post_id, user_id, f"User{user_id}")
                for user_id in user_ids
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        successful = sum(1 for success, _, _, _ in results if success)
        
        time.sleep(0.5)
        
        final_count = get_final_like_count(post_id, creator_token)
        
        if final_count == likes_per_post:
            print(f"   ✅ {successful}/{likes_per_post} likes, count: {final_count}")
        else:
            print(f"   ❌ {successful}/{likes_per_post} likes, count: {final_count} (expected {likes_per_post})")
            all_passed = False
    
    return all_passed


def main():
    """Run all race condition tests"""
    print("\n" + "=" * 60)
    print("🧪 RACE CONDITION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: Concurrent likes from different users
    results.append(("Concurrent Likes (10 users)", test_concurrent_likes(10)))
    
    # Test 2: More aggressive concurrent test
    results.append(("Concurrent Likes (50 users)", test_concurrent_likes(50)))
    
    # Test 3: Toggle spam from same user
    results.append(("Like/Unlike Toggle (20 ops)", test_concurrent_like_unlike(20)))
    
    # Test 4: Stress test
    results.append(("Stress Test (5×10)", test_stress(5, 10)))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "=" * 60)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
    else:
        print(f"⚠️  SOME TESTS FAILED ({passed}/{total} passed)")
    print("=" * 60)


if __name__ == "__main__":
    main()
