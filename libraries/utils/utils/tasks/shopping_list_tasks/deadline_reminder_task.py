"""Deadline reminder task - sends notifications for upcoming shopping deadlines."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_

from utils.api.endpoint import success
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.user import User
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)


class DeadlineReminderTask(BaseTask):
    """Check shopping lists for upcoming deadlines and send reminders.

    This task runs periodically (via Celery Beat) to:
    1. Find shopping list items with approaching deadlines
    2. Group items by user and shopping list
    3. Send push notifications to users who have notifications enabled

    Notification thresholds:
    - 2 hours before due: "Urgent" reminder
    - 24 hours before due: "Today" reminder
    - Items overdue: "Overdue" alert
    """

    name = "shopping_list_deadline_reminder"

    def execute(self):
        """Check for deadline reminders and send notifications.

        Returns:
            Success response with counts of notifications sent.
        """
        now = datetime.utcnow()

        # Time thresholds
        urgent_threshold = now + timedelta(hours=2)
        today_threshold = now + timedelta(hours=24)

        # Find items that need reminders
        reminders = self._find_items_needing_reminders(now, urgent_threshold, today_threshold)

        # Group by user
        user_reminders = self._group_by_user(reminders)

        # Send notifications
        notifications_sent = 0
        for user_id, user_data in user_reminders.items():
            sent = self._send_user_notifications(user_id, user_data)
            notifications_sent += sent

        logger.info(
            "Deadline reminder task completed: %d notifications sent",
            notifications_sent,
        )

        return success({
            "notifications_sent": notifications_sent,
            "users_notified": len(user_reminders),
            "items_processed": len(reminders),
        })

    def _find_items_needing_reminders(
        self,
        now: datetime,
        urgent_threshold: datetime,
        today_threshold: datetime,
    ) -> list[dict]:
        """Find all items with approaching or passed deadlines.

        Args:
            now: Current timestamp
            urgent_threshold: Cutoff for urgent reminders (2h)
            today_threshold: Cutoff for today reminders (24h)

        Returns:
            List of item data with urgency levels
        """
        reminders = []

        # Query items with due dates within the next 24 hours or overdue
        items = (
            self.database.db.query(ShoppingListItem)
            .join(ShoppingList)
            .filter(
                ShoppingListItem.is_checked == False,  # noqa: E712
                ShoppingListItem.due_at.isnot(None),
                ShoppingListItem.due_at <= today_threshold,
            )
            .all()
        )

        for item in items:
            # Determine urgency level
            if item.due_at < now:
                urgency = "overdue"
            elif item.due_at <= urgent_threshold:
                urgency = "urgent"
            else:
                urgency = "today"

            # Check if we already sent a reminder for this urgency level
            # (Using a simple check based on last reminder - could be stored in DB)
            if self._should_send_reminder(item, urgency):
                reminders.append({
                    "item": item,
                    "shopping_list": item.shopping_list,
                    "urgency": urgency,
                    "due_at": item.due_at,
                    "time_until": item.due_at - now,
                })

        return reminders

    def _should_send_reminder(self, item: ShoppingListItem, urgency: str) -> bool:
        """Check if we should send a reminder for this item.

        Avoids sending duplicate reminders by checking reminder history.
        For now, we use a simple approach - could be enhanced with
        a last_reminder_sent field on the item.

        Args:
            item: The shopping list item
            urgency: The current urgency level

        Returns:
            True if reminder should be sent
        """
        # Simple implementation: always send for now
        # Could be enhanced to track last_reminder_sent_at and urgency_level
        return True

    def _group_by_user(self, reminders: list[dict]) -> dict[str, dict]:
        """Group reminders by user for efficient notification sending.

        Args:
            reminders: List of reminder data

        Returns:
            Dict mapping user_id to their reminders and preferences
        """
        user_reminders: dict[str, dict] = {}

        for reminder in reminders:
            shopping_list = reminder["shopping_list"]

            # Get owner
            owner_id = str(shopping_list.owner_id)
            if owner_id not in user_reminders:
                owner = self.database.find_by(User, id=shopping_list.owner_id)
                user_reminders[owner_id] = {
                    "user": owner,
                    "notify_on_deadline": True,  # Owners always get deadline notifications
                    "reminders": [],
                }
            user_reminders[owner_id]["reminders"].append(reminder)

            # Get members with deadline notifications enabled
            members = (
                self.database.db.query(ShoppingListUser)
                .filter(
                    ShoppingListUser.shopping_list_id == shopping_list.id,
                    ShoppingListUser.notify_on_deadline == True,  # noqa: E712
                    ShoppingListUser.archived_at.is_(None),
                )
                .all()
            )

            for member in members:
                user_id = str(member.user_id)
                if user_id not in user_reminders:
                    user = self.database.find_by(User, id=member.user_id)
                    user_reminders[user_id] = {
                        "user": user,
                        "notify_on_deadline": True,
                        "reminders": [],
                    }
                user_reminders[user_id]["reminders"].append(reminder)

        return user_reminders

    def _send_user_notifications(self, user_id: str, user_data: dict) -> int:
        """Send notifications to a user about their upcoming deadlines.

        Args:
            user_id: The user's ID
            user_data: User data and their reminders

        Returns:
            Number of notifications sent
        """
        user = user_data["user"]
        reminders = user_data["reminders"]

        if not user or not reminders:
            return 0

        # Group by shopping list for cleaner notifications
        by_list: dict[str, list] = {}
        for reminder in reminders:
            list_id = str(reminder["shopping_list"].id)
            if list_id not in by_list:
                by_list[list_id] = {
                    "list_name": reminder["shopping_list"].name,
                    "items": [],
                }
            by_list[list_id]["items"].append(reminder)

        notifications_sent = 0

        for list_id, list_data in by_list.items():
            items = list_data["items"]

            # Determine overall urgency (use most urgent)
            urgencies = [r["urgency"] for r in items]
            if "overdue" in urgencies:
                overall_urgency = "overdue"
            elif "urgent" in urgencies:
                overall_urgency = "urgent"
            else:
                overall_urgency = "today"

            # Build notification
            notification = self._build_notification(
                list_name=list_data["list_name"],
                items=items,
                urgency=overall_urgency,
            )

            # Send push notification
            sent = self._send_push_notification(user, notification)
            if sent:
                notifications_sent += 1

        return notifications_sent

    def _build_notification(
        self,
        list_name: str,
        items: list[dict],
        urgency: str,
    ) -> dict:
        """Build notification content.

        Args:
            list_name: Name of the shopping list
            items: List of item reminders
            urgency: Overall urgency level

        Returns:
            Notification data dict
        """
        item_count = len(items)

        if urgency == "overdue":
            title = f"Overdue: {list_name}"
            body = (
                f"You have {item_count} overdue item(s) that need to be purchased!"
            )
        elif urgency == "urgent":
            title = f"Shop Soon: {list_name}"
            body = f"{item_count} item(s) due within 2 hours"
        else:
            title = f"Shopping Reminder: {list_name}"
            body = f"{item_count} item(s) to buy today"

        # Add item names if only a few
        if item_count <= 3:
            item_names = [r["item"].name for r in items]
            body = f"{body}\n{', '.join(item_names)}"

        return {
            "title": title,
            "body": body,
            "data": {
                "type": "shopping_deadline",
                "urgency": urgency,
                "item_count": item_count,
            },
        }

    def _send_push_notification(self, user: User, notification: dict) -> bool:
        """Send a push notification to a user.

        Args:
            user: The user to notify
            notification: Notification content

        Returns:
            True if notification was sent successfully
        """
        # TODO: Implement actual push notification via Firebase/APNs
        # For now, just log the notification
        logger.info(
            "Would send notification to user %s: %s - %s",
            user.id,
            notification["title"],
            notification["body"],
        )
        return True


# Register the task with Celery
deadline_reminder_task = celery_app.register_task(DeadlineReminderTask())
