"""
Firebase Cloud Messaging (FCM) Notification Service
Handles sending push notifications to mobile devices
"""
import json
import logging
import os
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Global Firebase Admin instance
_firebase_app = None
_fcm_enabled = False


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    global _firebase_app, _fcm_enabled
    
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
        
        # Check if Firebase credentials file exists
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
        
        if not os.path.exists(cred_path):
            logger.warning(f"❌ Firebase credentials not found at {cred_path}. Push notifications disabled.")
            _fcm_enabled = False
            return False
        
        # Initialize Firebase Admin
        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        _fcm_enabled = True
        
        logger.info("✅ Firebase Cloud Messaging initialized successfully")
        return True
        
    except ImportError:
        logger.warning("❌ firebase-admin package not installed. Push notifications disabled.")
        logger.warning("   Install with: pip install firebase-admin")
        _fcm_enabled = False
        return False
    except Exception as e:
        logger.error(f"❌ Failed to initialize Firebase: {e}")
        _fcm_enabled = False
        return False


def is_fcm_enabled() -> bool:
    """Check if FCM is enabled and initialized"""
    return _fcm_enabled


async def load_notification_tokens() -> Dict[str, List[str]]:
    """
    Load FCM tokens from JSON file
    Format: {user_id: [token1, token2, ...]}
    """
    from Config import get_data_dir
    token_file = f"{get_data_dir()}/notification_tokens.json"
    os.makedirs(os.path.dirname(token_file), exist_ok=True)
    
    if not os.path.exists(token_file):
        with open(token_file, 'w') as f:
            json.dump({}, f)
        return {}
    
    try:
        with open(token_file, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error("Error loading notification_tokens.json")
        return {}


async def save_notification_tokens(tokens: Dict[str, List[str]]) -> None:
    """Save FCM tokens to JSON file"""
    from Config import get_data_dir
    token_file = f"{get_data_dir()}/notification_tokens.json"
    with open(token_file, 'w') as f:
        json.dump(tokens, f, indent=2)


async def register_token(user_id: str, fcm_token: str, device_info: Optional[str] = None) -> bool:
    """
    Register or update FCM token for a user
    
    Args:
        user_id: Discord user ID
        fcm_token: Firebase Cloud Messaging token
        device_info: Optional device information
    
    Returns:
        True if successful, False otherwise
    """
    try:
        tokens = await load_notification_tokens()
        
        # Convert user_id to string for consistent JSON storage
        user_id_str = str(user_id)
        
        if user_id_str not in tokens:
            tokens[user_id_str] = []
        
        # Add token if not already registered
        if fcm_token not in tokens[user_id_str]:
            tokens[user_id_str].append(fcm_token)
            await save_notification_tokens(tokens)
            logger.info(f"✅ Registered FCM token for user {user_id}")
            return True
        
        logger.info(f"ℹ️ FCM token already registered for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to register FCM token: {e}")
        return False


async def unregister_token(user_id: str, fcm_token: str) -> bool:
    """
    Remove FCM token for a user
    
    Args:
        user_id: Discord user ID
        fcm_token: Firebase Cloud Messaging token
    
    Returns:
        True if successful, False otherwise
    """
    try:
        tokens = await load_notification_tokens()
        user_id_str = str(user_id)
        
        if user_id_str in tokens and fcm_token in tokens[user_id_str]:
            tokens[user_id_str].remove(fcm_token)
            
            # Remove user entry if no tokens left
            if not tokens[user_id_str]:
                del tokens[user_id_str]
            
            await save_notification_tokens(tokens)
            logger.info(f"✅ Unregistered FCM token for user {user_id}")
            return True
        
        logger.warning(f"⚠️ Token not found for user {user_id}")
        return False
        
    except Exception as e:
        logger.error(f"❌ Failed to unregister FCM token: {e}")
        return False


def load_notification_settings() -> Dict[str, Dict[str, bool]]:
    """
    Load notification settings from JSON file
    Format: {user_id: {setting_name: enabled}}
    """
    from Config import get_data_dir
    settings_file = f"{get_data_dir()}/notification_settings.json"
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    
    if not os.path.exists(settings_file):
        with open(settings_file, 'w') as f:
            json.dump({}, f)
        return {}
    
    try:
        with open(settings_file, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error("Error loading notification_settings.json")
        return {}


def save_notification_settings(settings: Dict[str, Dict[str, bool]]) -> None:
    """Save notification settings to JSON file"""
    from Config import get_data_dir
    settings_file = f"{get_data_dir()}/notification_settings.json"
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)


def get_user_notification_settings(user_id: str) -> Dict[str, bool]:
    """
    Get notification settings for a user
    
    Returns default settings if user has no custom settings
    """
    settings = load_notification_settings()
    user_id_str = str(user_id)
    
    # Default settings (all enabled)
    default_settings = {
        'ticket_new_messages': True,
        'ticket_mentions': True,
        'ticket_created': True,  # Only for admins/mods
        'ticket_assigned': True,
    }
    
    return settings.get(user_id_str, default_settings)


def update_user_notification_settings(user_id: str, new_settings: Dict[str, bool]) -> bool:
    """
    Update notification settings for a user
    
    Args:
        user_id: Discord user ID
        new_settings: Dictionary of setting_name: enabled pairs
    
    Returns:
        True if successful, False otherwise
    """
    try:
        settings = load_notification_settings()
        user_id_str = str(user_id)
        
        if user_id_str not in settings:
            settings[user_id_str] = {}
        
        # Update settings
        settings[user_id_str].update(new_settings)
        
        save_notification_settings(settings)
        logger.info(f"✅ Updated notification settings for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to update notification settings: {e}")
        return False


async def check_user_notification_enabled(user_id: str, notification_type: str) -> bool:
    """
    Check if a specific notification type is enabled for a user
    
    Args:
        user_id: Discord user ID
        notification_type: Type of notification (ticket_new_messages, ticket_mentions, etc.)
    
    Returns:
        True if enabled, False otherwise
    """
    settings = await get_user_notification_settings(user_id)
    return settings.get(notification_type, True)  # Default to True if not set


async def send_notification(
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    notification_type: Optional[str] = None
) -> bool:
    """
    Send push notification to a user's registered devices
    
    Args:
        user_id: Discord user ID
        title: Notification title
        body: Notification body text
        data: Optional data payload (e.g., ticket_id, notification_type)
        notification_type: Type of notification for settings check
    
    Returns:
        True if at least one notification was sent successfully
    """
    if not _fcm_enabled:
        logger.debug(f"FCM disabled, skipping notification for user {user_id}")
        return False
    
    # Check if user has this notification type enabled
    if notification_type:
        if not await check_user_notification_enabled(user_id, notification_type):
            logger.info(f"User {user_id} has {notification_type} disabled, skipping notification")
            return False
    
    try:
        from firebase_admin import messaging
        
        # Get user's FCM tokens
        tokens = await load_notification_tokens()
        user_id_str = str(user_id)
        
        if user_id_str not in tokens or not tokens[user_id_str]:
            logger.debug(f"No FCM tokens registered for user {user_id}")
            return False
        
        user_tokens = tokens[user_id_str]
        
        # Prepare notification data
        notification_data = data or {}
        notification_data['click_action'] = 'FLUTTER_NOTIFICATION_CLICK'
        
        # Convert all data values to strings (FCM requirement)
        notification_data = {k: str(v) for k, v in notification_data.items()}
        
        # Create message
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=notification_data,
            tokens=user_tokens,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    channel_id='hazebot_tickets',
                ),
            ),
        )
        
        # Send notification
        response = messaging.send_multicast(message)
        
        # Handle failed tokens
        if response.failure_count > 0:
            failed_tokens = []
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    failed_tokens.append(user_tokens[idx])
                    logger.warning(f"Failed to send to token {idx}: {resp.exception}")
            
            # Remove invalid tokens
            if failed_tokens:
                tokens[user_id_str] = [t for t in user_tokens if t not in failed_tokens]
                if not tokens[user_id_str]:
                    del tokens[user_id_str]
                await save_notification_tokens(tokens)
                logger.info(f"Removed {len(failed_tokens)} invalid tokens for user {user_id}")
        
        success = response.success_count > 0
        if success:
            logger.info(f"✅ Sent notification to user {user_id} ({response.success_count}/{len(user_tokens)} devices)")
        else:
            logger.warning(f"⚠️ Failed to send notification to user {user_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Error sending notification: {e}")
        return False


async def send_notification_to_multiple_users(
    user_ids: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    notification_type: Optional[str] = None
) -> int:
    """
    Send notification to multiple users
    
    Returns:
        Number of users successfully notified
    """
    success_count = 0
    
    for user_id in user_ids:
        if await send_notification(user_id, title, body, data, notification_type):
            success_count += 1
    
    return success_count
