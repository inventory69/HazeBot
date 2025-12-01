"""
Firebase Cloud Messaging (FCM) Notification Service
Handles sending push notifications to mobile devices

Design goals:
- Expose async APIs so callers in async contexts can await them
- Run blocking file I/O and firebase-admin network calls in a threadpool
  (using asyncio.to_thread) to avoid blocking the event loop
"""

import json
import logging
import os
import asyncio
import re
import html as html_module
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Global Firebase Admin instance
_firebase_app = None
_fcm_enabled = False


def strip_formatting(text: str) -> str:
    """Remove HTML/Markdown formatting from notification text

    Args:
        text: Text with potential HTML/Markdown formatting

    Returns:
        Plain text without formatting tags
    """
    if not text:
        return text

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Remove Markdown bold (**text**)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)

    # Remove Markdown italic (*text* or _text_)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # Remove Markdown strikethrough (~~text~~)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)

    # Remove Markdown code (`code`)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Unescape HTML entities (&amp; -> &, &lt; -> <, etc.)
    text = html_module.unescape(text)

    # Remove extra whitespace
    text = " ".join(text.split())

    return text.strip()


def initialize_firebase() -> bool:
    """Initialize Firebase Admin SDK (synchronous init)

    This is called at startup. It is OK for it to be synchronous since it
    performs one-time initialization.
    """
    global _firebase_app, _fcm_enabled

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check if Firebase credentials file exists
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")

        if not os.path.exists(cred_path):
            logger.warning(f"❌ Firebase credentials not found at {cred_path}. Push notifications disabled.")
            _fcm_enabled = False
            return False

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
    """Load FCM tokens from JSON file in a thread to avoid blocking."""
    from Config import get_data_dir

    token_file = f"{get_data_dir()}/notification_tokens.json"
    os.makedirs(os.path.dirname(token_file), exist_ok=True)

    def _read_tokens():
        logger.debug(f"📂 Loading tokens from: {token_file}")
        if not os.path.exists(token_file):
            logger.warning(f"⚠️ Token file not found, creating: {token_file}")
            with open(token_file, "w") as f:
                json.dump({}, f)
            return {}

        try:
            with open(token_file, "r") as f:
                tokens = json.load(f)
                logger.info(f"📱 Loaded {len(tokens)} user(s) with FCM tokens from {token_file}")
                logger.debug(f"📱 User IDs in tokens: {list(tokens.keys())}")
                return tokens
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error loading notification_tokens.json: {e}")
            return {}

    return await asyncio.to_thread(_read_tokens)


async def save_notification_tokens(tokens: Dict[str, List[str]]) -> None:
    """Save FCM tokens to JSON file in a thread."""
    from Config import get_data_dir

    token_file = f"{get_data_dir()}/notification_tokens.json"

    def _write_tokens():
        with open(token_file, "w") as f:
            json.dump(tokens, f, indent=2)

    await asyncio.to_thread(_write_tokens)


async def register_token(user_id: str, fcm_token: str, device_info: Optional[str] = None) -> bool:
    """Register or update FCM token for a user."""
    try:
        tokens = await load_notification_tokens()

        user_id_str = str(user_id)
        logger.info(f"🔐 Registering FCM token for user_id={user_id} (as string: '{user_id_str}')")
        logger.debug(f"🔐 Device info: {device_info}")
        logger.debug(f"🔐 Token preview: {fcm_token[:50]}...")

        if user_id_str not in tokens:
            tokens[user_id_str] = []
            logger.debug(f"🔐 Created new token list for user {user_id_str}")

        if fcm_token not in tokens[user_id_str]:
            tokens[user_id_str].append(fcm_token)
            await save_notification_tokens(tokens)
            logger.info(f"✅ Registered NEW FCM token for user {user_id} (total: {len(tokens[user_id_str])} tokens)")
            return True

        logger.info(f"ℹ️ FCM token already registered for user {user_id} (no changes needed)")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to register FCM token: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


async def unregister_token(user_id: str, fcm_token: str) -> bool:
    """Remove FCM token for a user."""
    try:
        tokens = await load_notification_tokens()
        user_id_str = str(user_id)

        if user_id_str in tokens and fcm_token in tokens[user_id_str]:
            tokens[user_id_str].remove(fcm_token)
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


async def load_notification_settings() -> Dict[str, Dict[str, bool]]:
    """Load notification settings from JSON file in a thread."""
    from Config import get_data_dir

    settings_file = f"{get_data_dir()}/notification_settings.json"
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)

    def _read_settings():
        if not os.path.exists(settings_file):
            with open(settings_file, "w") as f:
                json.dump({}, f)
            return {}

        try:
            with open(settings_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Error loading notification_settings.json")
            return {}

    return await asyncio.to_thread(_read_settings)


async def save_notification_settings(settings: Dict[str, Dict[str, bool]]) -> None:
    """Save notification settings to JSON file in a thread."""
    from Config import get_data_dir

    settings_file = f"{get_data_dir()}/notification_settings.json"

    def _write_settings():
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)

    await asyncio.to_thread(_write_settings)


async def get_user_notification_settings(user_id: str) -> Dict[str, bool]:
    """Get notification settings for a user. Returns defaults if none exist."""
    settings = await load_notification_settings()
    user_id_str = str(user_id)

    default_settings = {
        "ticket_new_messages": True,
        "ticket_mentions": True,
        "ticket_created": True,
        "ticket_assigned": True,
    }

    return settings.get(user_id_str, default_settings)


async def update_user_notification_settings(user_id: str, new_settings: Dict[str, bool]) -> bool:
    """Update and persist a user's notification settings."""
    try:
        settings = await load_notification_settings()
        user_id_str = str(user_id)

        if user_id_str not in settings:
            settings[user_id_str] = {}

        settings[user_id_str].update(new_settings)
        await save_notification_settings(settings)
        logger.info(f"✅ Updated notification settings for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to update notification settings: {e}")
        return False


async def check_user_notification_enabled(user_id: str, notification_type: str) -> bool:
    """Return whether a specific notification type is enabled for a user."""
    settings = await get_user_notification_settings(user_id)

    # First check if notifications are globally enabled for this user
    if not settings.get("notifications_enabled", True):
        return False

    # Then check the specific notification type
    return settings.get(notification_type, True)


async def send_notification(
    user_id: str, title: str, body: str, data: Optional[Dict[str, Any]] = None, notification_type: Optional[str] = None
) -> bool:
    """Send push notification to a user's registered devices.

    Uses asyncio.to_thread for the firebase-admin send so the event loop is
    not blocked by network/IO.
    """
    if not _fcm_enabled:
        logger.debug(f"FCM disabled, skipping notification for user {user_id}")
        return False

    if notification_type:
        if not await check_user_notification_enabled(user_id, notification_type):
            logger.info(f"User {user_id} has {notification_type} disabled, skipping notification")
            return False

    try:
        from firebase_admin import messaging

        tokens = await load_notification_tokens()
        user_id_str = str(user_id)

        logger.debug(f"🔍 Looking for tokens for user_id={user_id} (as string: '{user_id_str}')")
        logger.debug(f"🔍 Available user IDs in tokens: {list(tokens.keys())}")
        logger.debug(f"🔍 Token dict has {len(tokens)} users total")

        if user_id_str not in tokens or not tokens[user_id_str]:
            logger.info(f"📱 No FCM tokens registered for user {user_id}")
            logger.debug(f"📱 Checked for user_id_str='{user_id_str}' in tokens keys: {list(tokens.keys())}")
            return False

        user_tokens = tokens[user_id_str]
        logger.info(f"📱 Found {len(user_tokens)} FCM token(s) for user {user_id}")

        # Strip formatting from title and body for clean notifications
        clean_title = strip_formatting(title) if title else title
        clean_body = strip_formatting(body) if body else body

        # Truncate body to reasonable length (100 chars)
        if clean_body and len(clean_body) > 100:
            clean_body = clean_body[:97] + "..."

        notification_data = data or {}
        notification_data["click_action"] = "FLUTTER_NOTIFICATION_CLICK"
        notification_data = {k: str(v) for k, v in notification_data.items()}

        # Extract ticket_id for grouping (if available)
        ticket_id = notification_data.get("ticket_id")
        group_key = f"ticket_{ticket_id}" if ticket_id else None

        # Send to each token individually
        success_count = 0
        failed_tokens = []

        for token in user_tokens:
            try:
                # Build AndroidNotification with grouping support
                android_notification = messaging.AndroidNotification(
                    sound="default",
                    channel_id="hazebot_tickets",
                    icon="ic_notification",  # Monochrome notification icon
                    color="#FF6B35",  # Orange accent color for icon tint
                )

                # Add grouping tag if we have a ticket_id
                if group_key:
                    android_notification.tag = group_key  # Groups notifications by ticket

                # ✅ FIX: Use data-only message to prevent Firebase auto-display
                # The app's background handler will show custom notification with grouping
                # Add title/body to data payload for the app to display
                notification_data["title"] = clean_title
                notification_data["body"] = clean_body

                message = messaging.Message(
                    data=notification_data,  # Data-only message (no notification payload)
                    token=token,
                    android=messaging.AndroidConfig(
                        priority="high",
                        # Remove notification config - data-only messages don't use it
                    ),
                )

                def _send_message(msg):
                    return messaging.send(msg)

                message_id = await asyncio.to_thread(_send_message, message)
                logger.info(f"📱 Sent to token: {message_id}")
                success_count += 1

            except Exception as token_error:
                logger.warning(f"❌ Failed to send to token: {token_error}")
                failed_tokens.append(token)

        # Remove failed tokens
        if failed_tokens:
            tokens[user_id_str] = [t for t in user_tokens if t not in failed_tokens]
            if not tokens[user_id_str]:
                del tokens[user_id_str]
            await save_notification_tokens(tokens)
            logger.info(f"🗑️ Removed {len(failed_tokens)} invalid tokens for user {user_id}")

        success = success_count > 0
        if success:
            logger.info(f"✅ Sent notification to user {user_id} ({success_count}/{len(user_tokens)} devices)")
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
    notification_type: Optional[str] = None,
) -> int:
    """Send notification to multiple users and return count of successes."""
    success_count = 0
    for user_id in user_ids:
        if await send_notification(user_id, title, body, data, notification_type):
            success_count += 1
    return success_count
