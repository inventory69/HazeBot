#!/usr/bin/env python3
"""
Test Script: Push Notification zu Flutter App senden
Sendet eine Test-Notification um das neue Monochrome Icon zu testen
"""

import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Utils.notification_service import initialize_firebase, send_notification, is_fcm_enabled


async def test_push_notification():
    """Sende eine Test Push Notification"""
    
    print("🧪 Testing Push Notification System")
    print("=" * 60)
    
    # 1. Initialize Firebase
    print("\n1️⃣ Initializing Firebase...")
    if not initialize_firebase():
        print("❌ Firebase initialization failed!")
        print("   Make sure firebase-credentials.json exists")
        return
    
    print("✅ Firebase initialized")
    
    if not is_fcm_enabled():
        print("❌ FCM is not enabled!")
        return
    
    # 2. Get FCM token from user
    print("\n2️⃣ FCM Token Input")
    print("   You can find your FCM token in the Flutter app console output")
    print("   Look for: '🔑 FCM Token: ...'")
    print()
    
    # Try to read from SharedPreferences backup if available
    token = None
    
    # Manual input as fallback
    if not token:
        token = input("Enter FCM Token (or 'q' to quit): ").strip()
        if token.lower() == 'q':
            print("Aborted.")
            return
    
    if not token:
        print("❌ No token provided!")
        return
    
    print(f"✅ Using token: {token[:20]}...{token[-20:]}")
    
    # 3. Register token temporarily for test user
    print("\n3️⃣ Registering FCM Token for test user...")
    from Utils.notification_service import register_token
    
    test_user_id = "test_user_123"
    await register_token(test_user_id, token, "Test Device")
    print(f"✅ Token registered for test user: {test_user_id}")
    
    # 4. Send test notification
    print("\n4️⃣ Sending Test Notification...")
    
    # Test data for notification
    notification_data = {
        "ticket_id": "test_ticket_001",
        "ticket_num": "1234",
        "event_type": "new_message",
        "message": "Test message content",
        "author": "Admin",
        "timestamp": "2025-11-30T20:00:00Z"
    }
    
    try:
        result = await send_notification(
            user_id=test_user_id,
            title="Test Ticket #1234",
            body="This is a test message to verify the notification icon ✨",
            data=notification_data,
            notification_type="ticket_new_messages"
        )
        
        if result:
            print("✅ Notification sent successfully!")
            print("\n📱 Check your device/emulator:")
            print("   1. Pull down the status bar")
            print("   2. Look for 'Test Ticket #1234' notification")
            print("   3. The icon should show your app icon (monochrome)")
            print("   4. NOT a white square anymore! 🎉")
        else:
            print("❌ Failed to send notification")
            
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_push_notification())
