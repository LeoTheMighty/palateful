"""Firebase Cloud Messaging push notification service.

FCM works for both iOS and Android. It's free for unlimited notifications.

Setup:
1. Create Firebase project at console.firebase.google.com
2. Download service account JSON from Project Settings > Service Accounts
3. Set FIREBASE_CREDENTIALS_JSON env var to the JSON content (or path)
4. For iOS: Upload APNs key to Firebase > Project Settings > Cloud Messaging
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications we send."""

    # Shopping list
    SHOPPING_ITEM_ADDED = "shopping_item_added"
    SHOPPING_ITEM_CHECKED = "shopping_item_checked"
    SHOPPING_LIST_SHARED = "shopping_list_shared"
    SHOPPING_DEADLINE_REMINDER = "shopping_deadline_reminder"
    SHOPPING_LIST_COMPLETE = "shopping_list_complete"

    # Recipe book
    RECIPE_BOOK_SHARED = "recipe_book_shared"
    RECIPE_ADDED = "recipe_added"

    # Meal events
    MEAL_EVENT_INVITE = "meal_event_invite"
    MEAL_EVENT_REMINDER = "meal_event_reminder"
    MEAL_EVENT_UPDATED = "meal_event_updated"

    # Friends
    FRIEND_REQUEST = "friend_request"
    FRIEND_REQUEST_ACCEPTED = "friend_request_accepted"

    # General
    MEMBER_JOINED = "member_joined"
    SYSTEM = "system"


@dataclass
class PushNotification:
    """Push notification to send."""

    title: str
    body: str
    notification_type: NotificationType
    data: dict[str, str] | None = None
    image_url: str | None = None
    # For iOS
    badge: int | None = None
    sound: str = "default"
    # For Android
    channel_id: str = "default"
    priority: str = "high"  # "high" or "normal"


class PushNotificationService:
    """Service for sending push notifications via Firebase Cloud Messaging.

    Usage:
        service = PushNotificationService()
        service.send_to_user(user, PushNotification(
            title="New Item Added",
            body="Partner added Milk to the shopping list",
            notification_type=NotificationType.SHOPPING_ITEM_ADDED,
            data={"shopping_list_id": "123", "item_id": "456"}
        ))
    """

    _initialized = False
    _app: firebase_admin.App | None = None

    def __init__(self):
        """Initialize Firebase Admin SDK if not already initialized."""
        if not PushNotificationService._initialized:
            self._initialize_firebase()

    def _initialize_firebase(self) -> None:
        """Initialize Firebase Admin SDK from environment."""
        try:
            # Check for existing initialization
            if firebase_admin._apps:
                PushNotificationService._app = firebase_admin.get_app()
                PushNotificationService._initialized = True
                return

            # Get credentials from environment
            creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
            creds_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")

            if creds_json:
                # JSON string in env var
                creds_dict = json.loads(creds_json)
                cred = credentials.Certificate(creds_dict)
            elif creds_path:
                # Path to JSON file
                cred = credentials.Certificate(creds_path)
            else:
                logger.warning(
                    "Firebase credentials not configured. "
                    "Set FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH"
                )
                return

            PushNotificationService._app = firebase_admin.initialize_app(cred)
            PushNotificationService._initialized = True
            logger.info("Firebase Admin SDK initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize Firebase: %s", e)

    @property
    def is_available(self) -> bool:
        """Check if Firebase is properly initialized."""
        return PushNotificationService._initialized and PushNotificationService._app is not None

    def send_to_token(
        self,
        token: str,
        notification: PushNotification,
    ) -> str | None:
        """Send a push notification to a specific device token.

        Args:
            token: FCM device token
            notification: The notification to send

        Returns:
            FCM message ID if successful, None otherwise
        """
        if not self.is_available:
            logger.warning("Firebase not available, skipping push notification")
            return None

        try:
            message = self._build_message(token, notification)
            response = messaging.send(message)
            logger.info("Successfully sent push notification: %s", response)
            return response

        except messaging.UnregisteredError:
            logger.warning("Token is no longer valid: %s", token[:20])
            return None

        except Exception as e:
            logger.error("Failed to send push notification: %s", e)
            return None

    def send_to_tokens(
        self,
        tokens: list[str],
        notification: PushNotification,
    ) -> dict[str, Any]:
        """Send a push notification to multiple device tokens.

        Args:
            tokens: List of FCM device tokens
            notification: The notification to send

        Returns:
            Dict with success_count, failure_count, and invalid_tokens
        """
        if not self.is_available:
            logger.warning("Firebase not available, skipping push notifications")
            return {"success_count": 0, "failure_count": len(tokens), "invalid_tokens": []}

        if not tokens:
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

        try:
            message = self._build_multicast_message(tokens, notification)
            response = messaging.send_each_for_multicast(message)

            # Track invalid tokens for cleanup
            invalid_tokens = []
            for idx, send_response in enumerate(response.responses):
                if not send_response.success:
                    if isinstance(send_response.exception, messaging.UnregisteredError):
                        invalid_tokens.append(tokens[idx])

            logger.info(
                "Sent %d/%d push notifications, %d invalid tokens",
                response.success_count,
                len(tokens),
                len(invalid_tokens),
            )

            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "invalid_tokens": invalid_tokens,
            }

        except Exception as e:
            logger.error("Failed to send multicast push notification: %s", e)
            return {"success_count": 0, "failure_count": len(tokens), "invalid_tokens": []}

    def send_to_user(
        self,
        user: Any,  # User model
        notification: PushNotification,
        db_session: Any = None,
    ) -> dict[str, Any]:
        """Send a push notification to all of a user's devices.

        Args:
            user: User model with push_tokens field
            notification: The notification to send
            db_session: Optional database session for cleaning up invalid tokens

        Returns:
            Dict with success_count, failure_count, and cleaned_tokens
        """
        tokens = user.push_tokens or []
        if not tokens:
            return {"success_count": 0, "failure_count": 0, "cleaned_tokens": 0}

        # Check user notification preferences
        prefs = user.notification_preferences or {}
        if not prefs.get("push_enabled", True):
            logger.debug("User %s has push notifications disabled", user.id)
            return {"success_count": 0, "failure_count": 0, "cleaned_tokens": 0}

        # Check quiet hours
        if self._is_quiet_hours(prefs):
            logger.debug("User %s is in quiet hours", user.id)
            return {"success_count": 0, "failure_count": 0, "cleaned_tokens": 0}

        result = self.send_to_tokens(tokens, notification)

        # Clean up invalid tokens
        cleaned_tokens = 0
        if result["invalid_tokens"] and db_session:
            cleaned_tokens = self._cleanup_invalid_tokens(
                user, result["invalid_tokens"], db_session
            )

        return {
            "success_count": result["success_count"],
            "failure_count": result["failure_count"],
            "cleaned_tokens": cleaned_tokens,
        }

    def send_to_users(
        self,
        users: list[Any],  # List of User models
        notification: PushNotification,
        db_session: Any = None,
    ) -> dict[str, Any]:
        """Send a push notification to multiple users.

        Args:
            users: List of User models
            notification: The notification to send
            db_session: Optional database session for cleaning up invalid tokens

        Returns:
            Dict with total counts
        """
        total_success = 0
        total_failure = 0
        total_cleaned = 0

        for user in users:
            result = self.send_to_user(user, notification, db_session)
            total_success += result["success_count"]
            total_failure += result["failure_count"]
            total_cleaned += result["cleaned_tokens"]

        return {
            "success_count": total_success,
            "failure_count": total_failure,
            "cleaned_tokens": total_cleaned,
            "users_notified": len(users),
        }

    def _build_message(
        self,
        token: str,
        notification: PushNotification,
    ) -> messaging.Message:
        """Build a Firebase message for a single token."""
        return messaging.Message(
            token=token,
            notification=messaging.Notification(
                title=notification.title,
                body=notification.body,
                image=notification.image_url,
            ),
            data=self._prepare_data(notification),
            android=self._build_android_config(notification),
            apns=self._build_apns_config(notification),
        )

    def _build_multicast_message(
        self,
        tokens: list[str],
        notification: PushNotification,
    ) -> messaging.MulticastMessage:
        """Build a Firebase multicast message."""
        return messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(
                title=notification.title,
                body=notification.body,
                image=notification.image_url,
            ),
            data=self._prepare_data(notification),
            android=self._build_android_config(notification),
            apns=self._build_apns_config(notification),
        )

    def _prepare_data(self, notification: PushNotification) -> dict[str, str]:
        """Prepare data payload (must be string values for FCM)."""
        data = {
            "notification_type": notification.notification_type.value,
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
        }
        if notification.data:
            for key, value in notification.data.items():
                data[key] = str(value) if not isinstance(value, str) else value
        return data

    def _build_android_config(
        self,
        notification: PushNotification,
    ) -> messaging.AndroidConfig:
        """Build Android-specific notification config."""
        return messaging.AndroidConfig(
            priority=notification.priority,
            notification=messaging.AndroidNotification(
                channel_id=notification.channel_id,
                sound=notification.sound,
                default_sound=True,
                default_vibrate_timings=True,
            ),
        )

    def _build_apns_config(
        self,
        notification: PushNotification,
    ) -> messaging.APNSConfig:
        """Build iOS-specific notification config."""
        return messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound=notification.sound,
                    badge=notification.badge,
                    content_available=True,
                ),
            ),
        )

    def _is_quiet_hours(self, prefs: dict) -> bool:
        """Check if current time is within user's quiet hours."""
        quiet_start = prefs.get("quiet_hours_start")
        quiet_end = prefs.get("quiet_hours_end")

        if not quiet_start or not quiet_end:
            return False

        try:
            # Parse times (format: "22:00")
            now = datetime.now()
            start_hour, start_min = map(int, quiet_start.split(":"))
            end_hour, end_min = map(int, quiet_end.split(":"))

            current_minutes = now.hour * 60 + now.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min

            # Handle overnight quiet hours (e.g., 22:00 - 08:00)
            if start_minutes > end_minutes:
                return current_minutes >= start_minutes or current_minutes < end_minutes
            else:
                return start_minutes <= current_minutes < end_minutes

        except (ValueError, AttributeError):
            return False

    def _cleanup_invalid_tokens(
        self,
        user: Any,
        invalid_tokens: list[str],
        db_session: Any,
    ) -> int:
        """Remove invalid tokens from user's push_tokens."""
        if not invalid_tokens or not user.push_tokens:
            return 0

        original_count = len(user.push_tokens)
        user.push_tokens = [t for t in user.push_tokens if t not in invalid_tokens]
        db_session.commit()

        cleaned = original_count - len(user.push_tokens)
        if cleaned:
            logger.info("Cleaned %d invalid tokens for user %s", cleaned, user.id)
        return cleaned


# Singleton instance
_push_service: PushNotificationService | None = None


def get_push_service() -> PushNotificationService:
    """Get the push notification service singleton."""
    global _push_service
    if _push_service is None:
        _push_service = PushNotificationService()
    return _push_service
