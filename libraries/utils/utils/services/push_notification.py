"""Firebase Cloud Messaging push notification service.

Two-mode service: when FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH
is set, pushes are delivered via Firebase Cloud Messaging; otherwise the
service runs in log-only mode, emitting what it would have sent so local
dev and tests never require real Firebase credentials.

Every send attempt logs its outcome (success, failure with FCM response,
quiet-hours suppression, invalid token cleanup) so a missing push is
always distinguishable from a silent drop. Send failures also persist an
`error_logs` row with `service="push_notifications"` for queryable
troubleshooting.

Setup:
1. Create Firebase project at console.firebase.google.com
2. Download service account JSON from Project Settings > Service Accounts
3. Set FIREBASE_CREDENTIALS_JSON env var to the JSON content (or
   FIREBASE_CREDENTIALS_PATH to a file path)
4. For iOS: upload APNs .p8 key to Firebase > Project Settings > Cloud
   Messaging. See docs/PUSH_NOTIFICATIONS.md for the full procedure.
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
    RECIPE_FORKED = "recipe_forked"
    RECIPE_NOTE_ADDED = "recipe_note_added"
    RECIPE_COOKED_BY_PARTNER = "recipe_cooked_by_partner"

    # Import pipeline
    IMPORT_NEEDS_REVIEW = "import_needs_review"
    IMPORT_FAILED = "import_failed"

    # Meal events
    MEAL_EVENT_INVITE = "meal_event_invite"
    MEAL_EVENT_INVITE_ACCEPTED = "meal_event_invite_accepted"
    MEAL_EVENT_REMINDER = "meal_event_reminder"
    MEAL_EVENT_UPDATED = "meal_event_updated"

    # Cook follow-ups (2h post-cook personal prompt)
    COOK_FEEDBACK_PROMPT = "cook_feedback_prompt"

    # Friends
    FRIEND_REQUEST = "friend_request"
    FRIEND_REQUEST_ACCEPTED = "friend_request_accepted"

    # Invitations
    INVITATION_RECEIVED = "invitation_received"
    INVITATION_ACCEPTED = "invitation_accepted"

    # General
    MEMBER_JOINED = "member_joined"
    SYSTEM = "system"

    # Admin-facing feedback inbox (fan-out from a user's `POST /v1/user/feedback`).
    NEW_FEEDBACK = "new_feedback"

    # Diagnostic — always bypasses per-user prefs; bypasses quiet hours
    # only when send_to_user is called with force=True.
    TEST = "test"


# Diagnostic types that always ignore per-user notification_preferences.
# (Admin test-push should fire regardless of the target user's prefs.)
_DIAGNOSTIC_TYPES = frozenset({NotificationType.TEST})


# The 6 user-facing notification categories. Every non-diagnostic
# NotificationType MUST map to exactly one of these in
# `_CATEGORY_FOR_TYPE` below; CI fails otherwise (see exhaustiveness
# assertion at module bottom).
NOTIFICATION_CATEGORIES = frozenset({
    "meals",
    "timers",
    "shopping",
    "partner_activity",
    "imports",
    "friends_invitations",
})


def categories_default() -> dict[str, bool]:
    """Default per-category opt-in dict for new users / missing prefs.

    Every category defaults to True. Used by the prefs PUT handler when
    persisting a fresh `notification_preferences.categories` blob, and
    referenced as the implicit default by `send_to_user` when a key is
    missing on an old payload.
    """
    return {key: True for key in NOTIFICATION_CATEGORIES}


# Maps each notification type to its user-facing opt-out category.
# Diagnostic types (TEST) are intentionally absent — they bypass
# category checks entirely.
_CATEGORY_FOR_TYPE: dict[NotificationType, str] = {
    NotificationType.SHOPPING_ITEM_ADDED: "shopping",
    NotificationType.SHOPPING_ITEM_CHECKED: "shopping",
    NotificationType.SHOPPING_LIST_SHARED: "shopping",
    NotificationType.SHOPPING_DEADLINE_REMINDER: "shopping",
    NotificationType.SHOPPING_LIST_COMPLETE: "shopping",
    NotificationType.RECIPE_BOOK_SHARED: "partner_activity",
    NotificationType.RECIPE_ADDED: "partner_activity",
    NotificationType.RECIPE_FORKED: "partner_activity",
    NotificationType.RECIPE_NOTE_ADDED: "partner_activity",
    NotificationType.RECIPE_COOKED_BY_PARTNER: "partner_activity",
    NotificationType.COOK_FEEDBACK_PROMPT: "partner_activity",
    NotificationType.IMPORT_NEEDS_REVIEW: "imports",
    NotificationType.IMPORT_FAILED: "imports",
    NotificationType.MEAL_EVENT_INVITE: "meals",
    # Back-fan (invitee → inviter) is partner activity, not meal logistics.
    NotificationType.MEAL_EVENT_INVITE_ACCEPTED: "partner_activity",
    NotificationType.MEAL_EVENT_REMINDER: "meals",
    NotificationType.MEAL_EVENT_UPDATED: "meals",
    NotificationType.FRIEND_REQUEST: "friends_invitations",
    NotificationType.FRIEND_REQUEST_ACCEPTED: "friends_invitations",
    NotificationType.INVITATION_RECEIVED: "friends_invitations",
    NotificationType.INVITATION_ACCEPTED: "friends_invitations",
    NotificationType.MEMBER_JOINED: "friends_invitations",
    # SYSTEM and NEW_FEEDBACK are admin/system-facing — treated as
    # diagnostic for category-suppression purposes (always allowed),
    # but quiet hours + master push_enabled still apply.
}


# Types that bypass per-category opt-out (master switch + quiet hours
# still apply). System messages and admin-facing feedback fan-out
# don't belong to any user-toggleable category.
_CATEGORY_BYPASS_TYPES = frozenset({
    NotificationType.SYSTEM,
    NotificationType.NEW_FEEDBACK,
})


def _resolve_category(notification_type: NotificationType) -> str | None:
    """Return the category key for a notification type, or None if it
    has no user-facing category (diagnostic / system / admin types)."""
    if notification_type in _DIAGNOSTIC_TYPES:
        return None
    if notification_type in _CATEGORY_BYPASS_TYPES:
        return None
    return _CATEGORY_FOR_TYPE.get(notification_type)


# Exhaustiveness check: every NotificationType must be either diagnostic,
# bypassed, or have a category mapping. Future epics adding a new type
# without extending this map will fail at import time (and CI).
_uncovered = {
    t for t in NotificationType
    if t not in _DIAGNOSTIC_TYPES
    and t not in _CATEGORY_BYPASS_TYPES
    and t not in _CATEGORY_FOR_TYPE
}
assert not _uncovered, (
    f"NotificationType(s) missing from _CATEGORY_FOR_TYPE / "
    f"_CATEGORY_BYPASS_TYPES / _DIAGNOSTIC_TYPES: {sorted(t.value for t in _uncovered)}. "
    "Every new notification type must declare its category mapping in "
    "libraries/utils/utils/services/push_notification.py."
)


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
    # For Android — must match the AndroidNotificationChannel id created
    # client-side in `app/lib/core/services/push_notification_service.dart`
    # (see `palatefulDefaultChannelId`). Changing this without a matching
    # client change will route pushes to the system fallback channel.
    channel_id: str = "palateful_default"
    priority: str = "high"  # "high" or "normal"


class PushNotificationService:
    """Service for sending push notifications via Firebase Cloud Messaging.

    Runs in one of two modes depending on env:
    - **Delivery mode** — FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH
      is set and valid. Pushes go to FCM.
    - **Log-only mode** — neither env var is set (or credentials are malformed).
      Sends log the payload shape and return `{log_only: True, message_id: "log-only"}`
      without touching the FCM SDK. Local dev default.

    Usage:
        service = PushNotificationService()
        service.send_to_user(user, PushNotification(
            title="New Item Added",
            body="Partner added Milk to the shopping list",
            notification_type=NotificationType.SHOPPING_ITEM_ADDED,
            data={"shopping_list_id": "123", "item_id": "456"}
        ))
    """

    _initialized: bool = False
    _app: firebase_admin.App | None = None
    _log_only: bool = False

    def __init__(self):
        """Initialize Firebase Admin SDK (or log-only mode) if not already initialized."""
        if not PushNotificationService._initialized:
            self._initialize_firebase()

    def _initialize_firebase(self) -> None:
        """Initialize Firebase Admin SDK from environment, or fall back to log-only."""
        # If Firebase was already initialized elsewhere (e.g. by another
        # service in the same process), reuse it.
        if firebase_admin._apps:
            PushNotificationService._app = firebase_admin.get_app()
            PushNotificationService._initialized = True
            PushNotificationService._log_only = False
            return

        creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        creds_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")

        if not creds_json and not creds_path:
            logger.info(
                "push_notifications: running in log-only mode "
                "(no FIREBASE_CREDENTIALS_JSON / FIREBASE_CREDENTIALS_PATH); "
                "no pushes will be delivered"
            )
            PushNotificationService._log_only = True
            PushNotificationService._initialized = True
            return

        try:
            if creds_json:
                cred = credentials.Certificate(json.loads(creds_json))
            else:
                cred = credentials.Certificate(creds_path)
            PushNotificationService._app = firebase_admin.initialize_app(cred)
            PushNotificationService._log_only = False
            PushNotificationService._initialized = True
            logger.info("push_notifications: Firebase Admin SDK initialized")
        except Exception as e:  # noqa: BLE001 — never raise from init
            logger.error(
                "push_notifications: credentials present but init failed (%s); "
                "falling back to log-only mode",
                e,
            )
            PushNotificationService._log_only = True
            PushNotificationService._initialized = True

    @property
    def log_only(self) -> bool:
        """True when no Firebase creds are configured — sends are logged, not delivered."""
        return PushNotificationService._log_only

    @property
    def is_available(self) -> bool:
        """True when Firebase is configured and pushes will actually be delivered."""
        return PushNotificationService._initialized and PushNotificationService._app is not None

    # ------------------------------------------------------------------
    # Send APIs
    # ------------------------------------------------------------------

    def send_to_token(
        self,
        token: str,
        notification: PushNotification,
    ) -> dict[str, Any]:
        """Send a push notification to a specific device token.

        Returns a dict with `message_id` (FCM id on success, "log-only"
        in log-only mode, None on failure), `log_only` flag, and `error`
        key on failure. Never raises.
        """
        type_value = notification.notification_type.value

        if self.log_only:
            logger.info(
                "push_notifications: [log-only] would send type=%s title=%r body=%r",
                type_value, notification.title, notification.body,
            )
            return {
                "message_id": "log-only",
                "log_only": True,
                "target": token[:20],
            }

        try:
            message = self._build_message(token, notification)
            message_id = messaging.send(message)
            logger.info(
                "push_notifications: sent type=%s message_id=%s",
                type_value, message_id,
            )
            return {"message_id": message_id, "log_only": False}
        except messaging.UnregisteredError:
            logger.warning(
                "push_notifications: token invalid type=%s token=%s…",
                type_value, token[:20],
            )
            return {
                "message_id": None,
                "log_only": False,
                "error": "unregistered",
            }
        except Exception as e:  # noqa: BLE001 — never raise out
            logger.error(
                "push_notifications: send failed type=%s err=%s: %s",
                type_value, type(e).__name__, e,
            )
            self._log_send_failure(
                error_type=type(e).__name__,
                detail=str(e),
                notification_type=type_value,
                target=token[:20],
            )
            return {
                "message_id": None,
                "log_only": False,
                "error": str(e),
            }

    def send_to_tokens(
        self,
        tokens: list[str],
        notification: PushNotification,
    ) -> dict[str, Any]:
        """Send a push notification to multiple device tokens."""
        type_value = notification.notification_type.value

        if not tokens:
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": [], "message_id": None}

        if self.log_only:
            logger.info(
                "push_notifications: [log-only] would multicast type=%s title=%r body=%r tokens=%d",
                type_value, notification.title, notification.body, len(tokens),
            )
            return {
                "success_count": len(tokens),
                "failure_count": 0,
                "invalid_tokens": [],
                "message_id": "log-only",
                "log_only": True,
            }

        try:
            message = self._build_multicast_message(tokens, notification)
            response = messaging.send_each_for_multicast(message)

            invalid_tokens = []
            first_message_id = None
            for idx, send_response in enumerate(response.responses):
                if send_response.success:
                    if first_message_id is None:
                        first_message_id = send_response.message_id
                elif isinstance(send_response.exception, messaging.UnregisteredError):
                    invalid_tokens.append(tokens[idx])

            logger.info(
                "push_notifications: multicast type=%s success=%d failure=%d invalid=%d",
                type_value, response.success_count, response.failure_count, len(invalid_tokens),
            )

            if response.failure_count and not invalid_tokens:
                # At least one send failed for a non-unregistered reason —
                # record an ops row so this is queryable.
                self._log_send_failure(
                    error_type="MulticastPartialFailure",
                    detail=(
                        f"success={response.success_count} failure={response.failure_count}"
                    ),
                    notification_type=type_value,
                    target=f"{len(tokens)} tokens",
                )

            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "invalid_tokens": invalid_tokens,
                "message_id": first_message_id,
                "log_only": False,
            }
        except Exception as e:  # noqa: BLE001 — never raise out
            logger.error(
                "push_notifications: multicast failed type=%s err=%s: %s",
                type_value, type(e).__name__, e,
            )
            self._log_send_failure(
                error_type=type(e).__name__,
                detail=str(e),
                notification_type=type_value,
                target=f"{len(tokens)} tokens",
            )
            return {
                "success_count": 0,
                "failure_count": len(tokens),
                "invalid_tokens": [],
                "message_id": None,
                "log_only": False,
                "error": str(e),
            }

    def send_to_user(
        self,
        user: Any,  # User model
        notification: PushNotification,
        db_session: Any = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Send a push notification to all of a user's devices.

        `force=True` bypasses BOTH per-user `push_enabled` preference AND
        quiet hours. Used by the admin test-push endpoint and for system-
        critical notifications. `NotificationType.TEST` additionally
        always bypasses per-user preferences regardless of `force`.
        """
        type_value = notification.notification_type.value
        is_diagnostic = notification.notification_type in _DIAGNOSTIC_TYPES

        prefs = user.notification_preferences or {}
        push_enabled = prefs.get("push_enabled", True)
        in_quiet = self._is_quiet_hours(prefs)

        base_result = {
            "success_count": 0,
            "failure_count": 0,
            "cleaned_tokens": 0,
            "log_only": self.log_only,
            "quiet_hours_active": in_quiet,
            "suppressed_by_prefs": False,
            "suppressed_by_category": False,
            "suppressed_by_quiet_hours": False,
            "message_id": None,
        }

        # Suppression order (locked by epic-notifications-foundation party-mode):
        #   1. master `push_enabled`         — kill switch, bypassed only by force / TEST
        #   2. per-category opt-out          — bypassed by force / TEST / SYSTEM / NEW_FEEDBACK
        #   3. quiet hours                   — bypassed by force only
        # `force` is the deliberate escape valve at the bottom; categories are
        # the user's specific opt-out and trump quiet hours suppression-wise.
        # Future contributors must not reorder these checks.

        # 1. Per-user master preference — diagnostic types always bypass.
        if not push_enabled and not force and not is_diagnostic:
            logger.info(
                "push_notifications: suppressed (user prefs disabled) user=%s type=%s",
                user.id, type_value,
            )
            return {**base_result, "suppressed_by_prefs": True}

        # 2. Per-category opt-out. Diagnostic / SYSTEM / NEW_FEEDBACK + force
        # all bypass. Legacy clients without `categories` get all-on; the
        # legacy `partner_activity` flat field still works as a fallback.
        category = _resolve_category(notification.notification_type)
        if category and not force:
            categories = prefs.get("categories")
            if isinstance(categories, dict):
                # New nested shape — default missing keys to True so an old
                # payload that includes `categories` but missed a freshly
                # added category doesn't silently opt the user out.
                category_enabled = categories.get(category, True) is not False
            elif category == "partner_activity":
                # Legacy flat-field fallback for old clients.
                category_enabled = prefs.get("partner_activity", True) is not False
            else:
                category_enabled = True

            if not category_enabled:
                logger.info(
                    "push_notifications: suppressed (category=%s) user=%s type=%s",
                    category, user.id, type_value,
                )
                return {**base_result, "suppressed_by_category": True}

        # 3. Quiet hours — `force=True` bypasses.
        if in_quiet and not force:
            logger.info(
                "push_notifications: suppressed (quiet hours) user=%s type=%s window=%s-%s",
                user.id, type_value,
                prefs.get("quiet_hours_start"), prefs.get("quiet_hours_end"),
            )
            return {**base_result, "suppressed_by_quiet_hours": True}

        tokens = user.push_tokens or []
        if not tokens:
            logger.info(
                "push_notifications: no tokens registered user=%s type=%s",
                user.id, type_value,
            )
            return base_result

        result = self.send_to_tokens(tokens, notification)

        cleaned_tokens = 0
        if result.get("invalid_tokens") and db_session is not None:
            cleaned_tokens = self._cleanup_invalid_tokens(
                user, result["invalid_tokens"], db_session
            )

        return {
            **base_result,
            "success_count": result.get("success_count", 0),
            "failure_count": result.get("failure_count", 0),
            "cleaned_tokens": cleaned_tokens,
            "message_id": result.get("message_id"),
            "log_only": result.get("log_only", self.log_only),
        }

    def send_to_users(
        self,
        users: list[Any],  # List of User models
        notification: PushNotification,
        db_session: Any = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Send a push notification to multiple users."""
        total_success = 0
        total_failure = 0
        total_cleaned = 0

        for user in users:
            result = self.send_to_user(user, notification, db_session, force=force)
            total_success += result["success_count"]
            total_failure += result["failure_count"]
            total_cleaned += result["cleaned_tokens"]

        return {
            "success_count": total_success,
            "failure_count": total_failure,
            "cleaned_tokens": total_cleaned,
            "users_notified": len(users),
            "log_only": self.log_only,
        }

    # ------------------------------------------------------------------
    # Message builders (unchanged from prior impl)
    # ------------------------------------------------------------------

    def _build_message(
        self,
        token: str,
        notification: PushNotification,
    ) -> messaging.Message:
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
        # content-available is intentionally NOT set: it marks the push as a
        # silent background wake, which makes iOS suppress the banner and
        # apply background-push throttling even when an alert payload is
        # present. All notifications we send are user-visible alerts.
        return messaging.APNSConfig(
            headers={"apns-priority": "10"},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound=notification.sound,
                    badge=notification.badge,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_quiet_hours(self, prefs: dict) -> bool:
        """Check if current time is within user's quiet hours."""
        quiet_start = prefs.get("quiet_hours_start")
        quiet_end = prefs.get("quiet_hours_end")

        if not quiet_start or not quiet_end:
            return False

        try:
            now = datetime.now()
            start_hour, start_min = map(int, quiet_start.split(":"))
            end_hour, end_min = map(int, quiet_end.split(":"))

            current_minutes = now.hour * 60 + now.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min

            # Handle overnight windows (e.g., 22:00 - 08:00)
            if start_minutes > end_minutes:
                return current_minutes >= start_minutes or current_minutes < end_minutes
            return start_minutes <= current_minutes < end_minutes
        except (ValueError, AttributeError):
            return False

    def _cleanup_invalid_tokens(
        self,
        user: Any,
        invalid_tokens: list[str],
        db_session: Any,
    ) -> int:
        """Remove invalid tokens from user's push_tokens and log the cleanup."""
        if not invalid_tokens or not user.push_tokens:
            return 0

        original_count = len(user.push_tokens)
        user.push_tokens = [t for t in user.push_tokens if t not in invalid_tokens]
        db_session.commit()

        cleaned = original_count - len(user.push_tokens)
        if cleaned:
            logger.info(
                "push_notifications: cleaned %d invalid tokens user=%s reason=unregistered",
                cleaned, user.id,
            )
        return cleaned

    def _log_send_failure(
        self,
        error_type: str,
        detail: str,
        notification_type: str,
        target: str,
    ) -> None:
        """Persist a send-failure row to error_logs (service="push_notifications").

        Uses its own DB session so it never interferes with the caller's
        transaction. Failures here are swallowed — logging is best-effort.
        """
        try:
            # Local imports so this module stays import-safe in environments
            # without a configured DB (tests, schema checks, etc).
            from utils.models.error_log import ErrorLog
            from utils.services.database import Database
        except Exception:
            logger.exception("push_notifications: error_logs module unavailable")
            return

        try:
            database = Database()
            try:
                message = (
                    f"push send failed type={notification_type} target={target} "
                    f"error={error_type}: {detail[:500]}"
                )
                error_log = ErrorLog(
                    error_type="PushSendFailure",
                    error_message=message,
                    service="push_notifications",
                )
                database.create(error_log)
            finally:
                database.close()
        except Exception:
            logger.exception("push_notifications: failed to write error_log row")


# Singleton instance
_push_service: PushNotificationService | None = None


def get_push_service() -> PushNotificationService:
    """Get the push notification service singleton."""
    global _push_service
    if _push_service is None:
        _push_service = PushNotificationService()
    return _push_service
