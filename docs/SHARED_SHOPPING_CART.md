# Shared Shopping Cart System - Design Document

## Overview

A real-time, collaborative shopping cart system that enables households to share shopping lists, sync updates instantly, and integrate deeply with meal planning calendars. The system provides deadline awareness, showing when ingredients are needed based on upcoming meal events.

---

## User Stories

### Primary Use Case
> "My partner and I want to share a real-time shopping list connected to our meal plan. When either of us checks off an item at the store, the other sees it immediately. We want to see when ingredients are due and get reminded about upcoming meals."

### Key Scenarios

1. **Shared Household Shopping**
   - Partner A adds "chicken breast" at home
   - Partner B sees it appear instantly on their phone at the grocery store
   - Partner B checks it off; Partner A sees the update in real-time

2. **Meal Plan Integration**
   - User creates meal event "Chicken Parm" for Saturday 6pm
   - Shopping list automatically shows: "4hr until Chicken Parm prep start"
   - Each ingredient shows its deadline (when it's needed by)

3. **Smart Due Dates**
   - Chicken breast needed by Friday 2pm (for marinating)
   - Tomatoes needed by Saturday 4pm (for cooking)
   - Items are sorted/highlighted by urgency

4. **Floating Widget**
   - Small corner widget shows item count and nearest deadline
   - Expands to full list on tap
   - Persists across app navigation

---

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Shared Shopping Cart System                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Flutter    │◄──►│  WebSocket   │◄──►│    Redis     │                   │
│  │    App       │    │   Gateway    │    │   Pub/Sub    │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│         │                   │                    │                           │
│         │                   │                    │                           │
│         ▼                   ▼                    ▼                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   REST API   │◄──►│   Celery     │◄──►│  PostgreSQL  │                   │
│  │  (FastAPI)   │    │   Worker     │    │   Database   │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                                               │
│  Real-time Flow:                                                             │
│  1. User checks item → REST API updates DB                                  │
│  2. API publishes event to Redis                                            │
│  3. WebSocket Gateway broadcasts to all connected users                     │
│  4. Flutter apps receive update, refresh UI instantly                       │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **Flutter App** | UI, local state, WebSocket connection, offline queue |
| **REST API** | CRUD operations, authorization, business logic |
| **WebSocket Gateway** | Real-time connections, room management, broadcasting |
| **Redis Pub/Sub** | Cross-instance message passing, presence tracking |
| **Celery Worker** | Deadline calculations, notifications, cleanup |
| **PostgreSQL** | Persistent storage, JSONB for flexible data |

---

## Data Models

### New Model: ShoppingListUser (Many-to-Many Sharing)

```python
# /libraries/utils/utils/models/shopping_list_user.py

class ShoppingListUser(JoinsBase):
    """Join table for shopping list membership/sharing."""

    __tablename__ = "shopping_list_users"

    # Composite primary key
    shopping_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("shopping_lists.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # Role: owner | editor | viewer
    role: Mapped[str] = mapped_column(String(20), default="editor")

    # Notification preferences per user per list
    notify_on_add: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_check: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_on_deadline: Mapped[bool] = mapped_column(Boolean, default=True)

    # Last seen cursor for unread tracking
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    shopping_list: Mapped["ShoppingList"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="shopping_list_memberships")

    __table_args__ = (
        UniqueConstraint("shopping_list_id", "user_id", name="uq_shopping_list_users"),
    )
```

### Extended: ShoppingList Model

```python
# Additions to /libraries/utils/utils/models/shopping_list.py

class ShoppingList(Base):
    """A shopping list that can be shared between users."""

    __tablename__ = "shopping_lists"

    # === Existing Fields ===
    name: Mapped[str | None]
    status: Mapped[str]  # pending | in_progress | completed
    meal_event_id: Mapped[uuid.UUID | None]
    pantry_id: Mapped[uuid.UUID | None]
    owner_id: Mapped[uuid.UUID]

    # === NEW: Sharing & Real-time ===

    # Whether this list is shared (enables real-time features)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)

    # Short code for easy sharing (e.g., "ABC123")
    share_code: Mapped[str | None] = mapped_column(String(10), unique=True, nullable=True)

    # Default deadline for items without explicit due dates
    default_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Whether to auto-populate from upcoming meal events
    auto_populate_from_calendar: Mapped[bool] = mapped_column(Boolean, default=True)

    # Calendar range for auto-population (days ahead)
    calendar_lookahead_days: Mapped[int] = mapped_column(Integer, default=7)

    # === NEW: Widget Display Settings ===

    # Color theme for the floating widget
    widget_color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # Hex color

    # Sort order preference
    sort_by: Mapped[str] = mapped_column(String(20), default="deadline")
    # Options: deadline | category | name | checked | added_at

    # === Relationships ===
    members: Mapped[list["ShoppingListUser"]] = relationship(
        back_populates="shopping_list", cascade="all, delete-orphan"
    )
    items: Mapped[list["ShoppingListItem"]] = relationship(
        back_populates="shopping_list", cascade="all, delete-orphan"
    )
```

### Extended: ShoppingListItem Model

```python
# Additions to /libraries/utils/utils/models/shopping_list.py

class ShoppingListItem(Base):
    """An item on a shopping list with deadline tracking."""

    __tablename__ = "shopping_list_items"

    # === Existing Fields ===
    name: Mapped[str]
    quantity: Mapped[Decimal | None]
    unit: Mapped[str | None]
    is_checked: Mapped[bool]
    checked_by_user_id: Mapped[uuid.UUID | None]
    recipe_id: Mapped[uuid.UUID | None]
    already_have_quantity: Mapped[Decimal | None]
    category: Mapped[str | None]
    shopping_list_id: Mapped[uuid.UUID]
    ingredient_id: Mapped[uuid.UUID | None]

    # === NEW: Deadline & Meal Event Integration ===

    # When this specific ingredient is needed by
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Which meal event this item is for (can differ from list's meal_event_id for aggregated lists)
    meal_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("meal_events.id", ondelete="SET NULL"), nullable=True
    )

    # Why this ingredient is needed at this time
    due_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Examples: "marinating", "prep_start", "cook_start", "serving"

    # Priority level (1-5, where 1 is most urgent)
    priority: Mapped[int] = mapped_column(Integer, default=3)

    # === NEW: Collaboration Features ===

    # Who added this item
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Optional note (e.g., "get organic", "brand X preferred")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # When the item was checked (for sorting/history)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Assignee (who should get this item)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # === NEW: Store Location Hints ===

    # Aisle or section in store
    store_section: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Store-specific ordering index
    store_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # === Relationships ===
    meal_event: Mapped["MealEvent | None"] = relationship()
    added_by: Mapped["User | None"] = relationship(foreign_keys=[added_by_user_id])
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_user_id])
```

### New Model: ShoppingListEvent (Activity Feed)

```python
# /libraries/utils/utils/models/shopping_list_event.py

class ShoppingListEvent(Base):
    """Activity log for real-time sync and history."""

    __tablename__ = "shopping_list_events"

    # Event type
    event_type: Mapped[str] = mapped_column(String(30))
    # Types: item_added | item_checked | item_unchecked | item_removed |
    #        item_updated | member_joined | member_left | list_updated

    # Event data (flexible JSONB for different event types)
    event_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Examples:
    # item_added: {"item_id": "...", "name": "Milk", "quantity": 1, "unit": "gallon"}
    # item_checked: {"item_id": "...", "name": "Eggs"}
    # member_joined: {"user_id": "...", "name": "Partner Name"}

    # Who triggered this event
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Which list
    shopping_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("shopping_lists.id", ondelete="CASCADE")
    )

    # Sequence number for ordering (auto-increment per list)
    sequence: Mapped[int] = mapped_column(Integer)

    # Relationships
    user: Mapped["User | None"] = relationship()
    shopping_list: Mapped["ShoppingList"] = relationship()

    __table_args__ = (
        Index("ix_shopping_list_events_list_sequence", "shopping_list_id", "sequence"),
    )
```

---

## Deadline Calculation System

### Due Date Hierarchy

Items can have due dates from multiple sources, resolved in this priority order:

```python
def calculate_item_due_date(item: ShoppingListItem) -> datetime | None:
    """Calculate when an ingredient is actually needed."""

    # 1. Explicit due date on item (user override)
    if item.due_at:
        return item.due_at

    # 2. Based on meal event prep requirements
    if item.meal_event_id:
        meal_event = get_meal_event(item.meal_event_id)
        recipe = meal_event.recipe

        if recipe and item.ingredient_id:
            # Find if this ingredient has prep-ahead requirements
            prep_time = get_ingredient_prep_time(recipe, item.ingredient_id)

            if prep_time:
                # e.g., "marinate 4 hours before" → due 4 hours before scheduled_at
                return meal_event.scheduled_at - timedelta(minutes=prep_time.lead_time_minutes)

        # Default: due at prep start time
        prep_offset = meal_event.prep_start_offset_minutes or 60
        return meal_event.scheduled_at - timedelta(minutes=prep_offset)

    # 3. Based on shopping list's default deadline
    if item.shopping_list.default_deadline:
        return item.shopping_list.default_deadline

    # 4. No deadline
    return None
```

### Due Reason Classification

```python
DUE_REASONS = {
    "marinating": "Needs time to marinate",
    "thawing": "Needs time to thaw",
    "rising": "Dough needs to rise",
    "brining": "Needs brining time",
    "chilling": "Needs to chill/set",
    "prep_start": "Prep begins",
    "cook_start": "Cooking begins",
    "serving": "Meal time",
}
```

### Urgency Levels

```python
def get_urgency_level(due_at: datetime | None) -> str:
    """Determine urgency for UI highlighting."""
    if not due_at:
        return "none"

    hours_until = (due_at - datetime.now(UTC)).total_seconds() / 3600

    if hours_until < 0:
        return "overdue"      # Red, past due
    elif hours_until < 2:
        return "urgent"       # Orange, very soon
    elif hours_until < 24:
        return "today"        # Yellow, same day
    elif hours_until < 72:
        return "soon"         # Blue, next few days
    else:
        return "normal"       # Gray, plenty of time
```

---

## Real-Time Sync System

### WebSocket Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     WebSocket Gateway Service                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Connection Management:                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ connections: Map<user_id, Set<WebSocket>>                │    │
│  │ rooms: Map<shopping_list_id, Set<user_id>>               │    │
│  │ presence: Map<shopping_list_id, Map<user_id, status>>    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Message Types:                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ subscribe    → Join a shopping list room                 │    │
│  │ unsubscribe  → Leave a shopping list room                │    │
│  │ item_update  → Broadcast item change to room             │    │
│  │ presence     → User online/offline/typing status         │    │
│  │ cursor       → Real-time cursor position (optional)      │    │
│  │ sync_request → Request full state sync                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Message Protocol

```typescript
// Client → Server
interface ClientMessage {
  type: "subscribe" | "unsubscribe" | "presence" | "sync_request";
  shopping_list_id?: string;
  data?: any;
}

// Server → Client
interface ServerMessage {
  type: "item_added" | "item_updated" | "item_removed" | "item_checked" |
        "member_joined" | "member_left" | "presence_update" | "sync_response" |
        "error";
  shopping_list_id: string;
  data: any;
  user_id?: string;        // Who triggered this
  timestamp: string;       // ISO 8601
  sequence: number;        // For ordering
}

// Example: Item Checked
{
  "type": "item_checked",
  "shopping_list_id": "abc-123",
  "data": {
    "item_id": "item-456",
    "name": "Milk",
    "checked": true,
    "checked_by": {
      "id": "user-789",
      "name": "Partner"
    }
  },
  "user_id": "user-789",
  "timestamp": "2026-01-30T15:30:00Z",
  "sequence": 42
}
```

### Sync Strategy

```python
# On WebSocket connect:
async def handle_connect(websocket, user_id):
    # 1. Get user's shared shopping lists
    lists = get_user_shopping_lists(user_id, shared_only=True)

    # 2. Subscribe to each list's Redis channel
    for list in lists:
        await redis.subscribe(f"shopping_list:{list.id}")

    # 3. Send current state
    for list in lists:
        items = get_list_items(list.id)
        members = get_list_members(list.id)
        await websocket.send({
            "type": "sync_response",
            "shopping_list_id": str(list.id),
            "data": {
                "items": items,
                "members": members,
                "last_sequence": get_last_sequence(list.id)
            }
        })

# On item update (via REST API):
async def update_item(item_id, updates, user_id):
    # 1. Update database
    item = update_item_in_db(item_id, updates)

    # 2. Create event record
    event = create_shopping_list_event(
        shopping_list_id=item.shopping_list_id,
        event_type="item_updated",
        event_data={"item_id": item_id, **updates},
        user_id=user_id
    )

    # 3. Publish to Redis for real-time broadcast
    await redis.publish(
        f"shopping_list:{item.shopping_list_id}",
        {
            "type": "item_updated",
            "shopping_list_id": str(item.shopping_list_id),
            "data": {"item_id": item_id, **updates},
            "user_id": str(user_id),
            "sequence": event.sequence
        }
    )

    return item
```

### Conflict Resolution

```python
# Last-write-wins with sequence numbers
def resolve_conflict(local_item, remote_update):
    """Resolve conflicts when offline changes sync."""

    if remote_update.sequence > local_item.last_synced_sequence:
        # Remote is newer, accept it
        return remote_update

    if local_item.updated_at > remote_update.timestamp:
        # Local is newer, push our version
        push_local_update(local_item)
        return local_item

    # Same time? Prefer checked > unchecked, then by user_id for determinism
    if local_item.is_checked != remote_update.is_checked:
        return local_item if local_item.is_checked else remote_update

    return remote_update if remote_update.user_id > local_item.updated_by else local_item
```

---

## Flutter UI: Floating Cart Widget

### Widget Hierarchy

```dart
// Overlay widget that floats above all screens
class FloatingCartWidget extends StatefulWidget {
  // Displays as:
  // ┌───────────────────┐
  // │ 🛒 8 items        │  ← Collapsed (tap to expand)
  // │ ⏰ 3h until prep  │
  // └───────────────────┘

  // Expanded:
  // ┌─────────────────────────────────────┐
  // │ Saturday Dinner Shopping     ▼ ✕   │
  // ├─────────────────────────────────────┤
  // │ ⚡ URGENT (due in 2h)              │
  // │ ☐ Chicken breast (marinating)      │
  // │ ───────────────────────────────────│
  // │ 📅 TODAY                           │
  // │ ☑ Olive oil ✓ Partner              │
  // │ ☐ Parmesan cheese                  │
  // │ ☐ Fresh basil                      │
  // │ ───────────────────────────────────│
  // │ 📦 ANYTIME                         │
  // │ ☐ Salt                             │
  // │ ───────────────────────────────────│
  // │ [+ Add item]           [📋 Full list]│
  // └─────────────────────────────────────┘
}
```

### Widget States

```dart
enum CartWidgetState {
  collapsed,    // Small pill showing count + next deadline
  expanded,     // Full list view
  minimized,    // Just icon, user dragged to corner
  hidden,       // User explicitly hid it
}

class CartWidgetPosition {
  // Draggable to any corner
  Alignment alignment;  // topLeft, topRight, bottomLeft, bottomRight
  Offset offset;        // Fine-tuned position
  bool isLocked;        // Prevent accidental moves
}
```

### Real-Time Updates UI

```dart
// When partner checks an item:
class ItemCheckAnimation extends StatelessWidget {
  // 1. Item slides to "checked" section
  // 2. Shows "✓ Partner" badge briefly
  // 3. Strikethrough animation
  // 4. Optional: celebration confetti for last item
}

// When new item added:
class ItemAddedAnimation extends StatelessWidget {
  // 1. Item slides in from left
  // 2. Highlight glow
  // 3. Shows "Added by Partner" toast
}

// Presence indicators:
class MemberPresence extends StatelessWidget {
  // Shows avatars of who's viewing:
  // [👤 You] [👤 Partner - shopping] [👤 Mom - viewing]
}
```

### Countdown Display

```dart
class MealCountdown extends StatelessWidget {
  final MealEvent mealEvent;

  // Displays:
  // "🍝 Chicken Parm"
  // "4h 23m until prep start"
  // or
  // "⚠️ Prep starts in 15 minutes!"
  // or
  // "🍳 Cooking now!"

  String get countdownText {
    final prepStart = mealEvent.scheduledAt.subtract(
      Duration(minutes: mealEvent.prepStartOffsetMinutes)
    );
    final remaining = prepStart.difference(DateTime.now());

    if (remaining.isNegative) {
      if (remaining.inMinutes > -mealEvent.cookStartOffsetMinutes) {
        return "🍳 Prep in progress";
      } else {
        return "🍽️ Meal time!";
      }
    }

    if (remaining.inMinutes < 30) {
      return "⚠️ Prep starts in ${remaining.inMinutes}m!";
    }

    return "${remaining.inHours}h ${remaining.inMinutes % 60}m until prep";
  }
}
```

---

## API Endpoints

### Shopping List Sharing

```
POST   /v1/shopping-lists/{list_id}/share
       Request: { "email": "partner@email.com", "role": "editor" }
       Response: { "share_code": "ABC123", "invite_sent": true }

POST   /v1/shopping-lists/join/{share_code}
       Response: { "shopping_list_id": "...", "role": "editor" }

GET    /v1/shopping-lists/{list_id}/members
       Response: { "members": [{ "user_id", "name", "role", "is_online" }] }

PUT    /v1/shopping-lists/{list_id}/members/{user_id}
       Request: { "role": "viewer" }

DELETE /v1/shopping-lists/{list_id}/members/{user_id}
       (Leave or remove member)
```

### Enhanced Item Operations

```
POST   /v1/shopping-lists/{list_id}/items
       Request: {
         "name": "Chicken breast",
         "quantity": 2,
         "unit": "lbs",
         "meal_event_id": "...",
         "due_at": "2026-01-30T14:00:00Z",
         "due_reason": "marinating",
         "notes": "Get organic",
         "assigned_to_user_id": "..."
       }

PATCH  /v1/shopping-lists/{list_id}/items/{item_id}/check
       Request: { "checked": true }
       (Simplified endpoint for quick check/uncheck)

PATCH  /v1/shopping-lists/{list_id}/items/{item_id}/assign
       Request: { "user_id": "..." }
```

### Calendar Integration

```
POST   /v1/shopping-lists/{list_id}/populate-from-calendar
       Request: {
         "start_date": "2026-01-30",
         "end_date": "2026-02-06",
         "check_pantry": true,
         "include_meal_event_ids": ["..."]  // Optional filter
       }
       Response: {
         "items_added": 15,
         "meal_events_included": 4,
         "items": [...]
       }

GET    /v1/shopping-lists/{list_id}/deadlines
       Response: {
         "next_deadline": "2026-01-30T14:00:00Z",
         "next_meal_event": { "id", "title", "scheduled_at", "prep_start_at" },
         "items_by_urgency": {
           "overdue": [...],
           "urgent": [...],
           "today": [...],
           "soon": [...],
           "normal": [...]
         }
       }
```

### Real-Time Sync

```
WS     /v1/ws/shopping-lists
       (WebSocket endpoint for real-time updates)

GET    /v1/shopping-lists/{list_id}/events
       Query: ?since_sequence=42
       Response: {
         "events": [...],
         "current_sequence": 57
       }
       (For catching up after disconnect)
```

---

## Notification System

### Notification Types

| Event | Recipients | Channels | Message |
|-------|------------|----------|---------|
| Item added | All members (except adder) | Push | "Partner added Milk to Saturday Shopping" |
| Item checked | Members w/ notify_on_check | Push | "Partner got the chicken!" |
| Deadline approaching | All members | Push + In-App | "⏰ Chicken breast needed in 2 hours for marinating" |
| Prep starting soon | All members | Push | "🍳 Start prepping Chicken Parm in 30 minutes!" |
| Member joined | All members | In-App | "Mom joined the shopping list" |
| List completed | All members | Push | "🎉 All items checked! Ready to cook!" |

### Notification Preferences

```python
class ShoppingNotificationPreferences:
    # Per-list settings (stored in ShoppingListUser)
    notify_on_add: bool = True       # When items added
    notify_on_check: bool = False    # When items checked (can be noisy)
    notify_on_deadline: bool = True  # Deadline reminders

    # Global settings (stored in User.notification_preferences)
    shopping_quiet_while_shopping: bool = True  # Silence during active shopping
    deadline_reminder_minutes: list[int] = [120, 30]  # When to remind (2h, 30m before)
```

---

## Database Migration

```python
# /services/migrator/migrations/versions/20260130_add_shared_shopping_cart.py

def upgrade():
    # 1. Create shopping_list_users table
    op.create_table(
        "shopping_list_users",
        sa.Column("shopping_list_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="editor"),
        sa.Column("notify_on_add", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_on_check", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notify_on_deadline", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("shopping_list_id", "user_id"),
        sa.ForeignKeyConstraint(["shopping_list_id"], ["shopping_lists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("shopping_list_id", "user_id", name="uq_shopping_list_users"),
    )

    # 2. Add columns to shopping_lists
    op.add_column("shopping_lists", sa.Column("is_shared", sa.Boolean(), server_default="false"))
    op.add_column("shopping_lists", sa.Column("share_code", sa.String(10), unique=True, nullable=True))
    op.add_column("shopping_lists", sa.Column("default_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopping_lists", sa.Column("auto_populate_from_calendar", sa.Boolean(), server_default="true"))
    op.add_column("shopping_lists", sa.Column("calendar_lookahead_days", sa.Integer(), server_default="7"))
    op.add_column("shopping_lists", sa.Column("widget_color", sa.String(7), nullable=True))
    op.add_column("shopping_lists", sa.Column("sort_by", sa.String(20), server_default="'deadline'"))

    # 3. Add columns to shopping_list_items
    op.add_column("shopping_list_items", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopping_list_items", sa.Column("meal_event_id", sa.UUID(), nullable=True))
    op.add_column("shopping_list_items", sa.Column("due_reason", sa.String(100), nullable=True))
    op.add_column("shopping_list_items", sa.Column("priority", sa.Integer(), server_default="3"))
    op.add_column("shopping_list_items", sa.Column("added_by_user_id", sa.UUID(), nullable=True))
    op.add_column("shopping_list_items", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("shopping_list_items", sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopping_list_items", sa.Column("assigned_to_user_id", sa.UUID(), nullable=True))
    op.add_column("shopping_list_items", sa.Column("store_section", sa.String(50), nullable=True))
    op.add_column("shopping_list_items", sa.Column("store_order", sa.Integer(), nullable=True))

    # 4. Add foreign keys for new columns
    op.create_foreign_key(
        "fk_shopping_list_items_meal_event",
        "shopping_list_items", "meal_events",
        ["meal_event_id"], ["id"],
        ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_shopping_list_items_added_by",
        "shopping_list_items", "users",
        ["added_by_user_id"], ["id"],
        ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_shopping_list_items_assigned_to",
        "shopping_list_items", "users",
        ["assigned_to_user_id"], ["id"],
        ondelete="SET NULL"
    )

    # 5. Create shopping_list_events table
    op.create_table(
        "shopping_list_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("event_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("shopping_list_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shopping_list_id"], ["shopping_lists.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_shopping_list_events_list_sequence",
        "shopping_list_events",
        ["shopping_list_id", "sequence"]
    )

    # 6. Create indexes for common queries
    op.create_index("ix_shopping_list_items_due_at", "shopping_list_items", ["due_at"])
    op.create_index("ix_shopping_list_items_meal_event_id", "shopping_list_items", ["meal_event_id"])
    op.create_index("ix_shopping_lists_share_code", "shopping_lists", ["share_code"])
```

---

## Implementation Phases

### Phase 1: Core Sharing (Week 1-2)
- [ ] ShoppingListUser model and migration
- [ ] Share/join API endpoints
- [ ] Member management endpoints
- [ ] Update existing shopping list endpoints for multi-user access

### Phase 2: Deadline System (Week 2-3)
- [ ] Extended ShoppingListItem fields
- [ ] Due date calculation logic
- [ ] Calendar population endpoint
- [ ] Urgency sorting and grouping

### Phase 3: Real-Time Sync (Week 3-4)
- [ ] WebSocket gateway service
- [ ] Redis pub/sub integration
- [ ] ShoppingListEvent model and activity logging
- [ ] Sync protocol implementation

### Phase 4: Flutter Widget (Week 4-5)
- [ ] Floating cart widget component
- [ ] Draggable positioning
- [ ] Expand/collapse animations
- [ ] Real-time update handling

### Phase 5: Notifications (Week 5-6)
- [ ] Deadline reminder worker task
- [ ] Push notification integration
- [ ] Notification preferences UI
- [ ] "Shopping mode" quiet period

### Phase 6: Polish (Week 6+)
- [ ] Offline support with sync queue
- [ ] Store section organization
- [ ] Item assignment and splitting
- [ ] Celebration animations

---

## Error Codes

Add to `/libraries/utils/utils/classes/error_code.py`:

```python
# Shopping List Sharing errors (180-199)
SHOPPING_LIST_NOT_SHARED = 180
SHOPPING_LIST_ALREADY_MEMBER = 181
SHOPPING_LIST_INVALID_SHARE_CODE = 182
SHOPPING_LIST_CANNOT_REMOVE_OWNER = 183
SHOPPING_LIST_MEMBER_NOT_FOUND = 184
SHOPPING_LIST_SHARE_LIMIT_REACHED = 185
SHOPPING_LIST_CANNOT_LEAVE_AS_OWNER = 186
```

---

## Security Considerations

1. **Share Code Generation**
   - 6-character alphanumeric, case-insensitive
   - Expires after 7 days or first use
   - Rate limit: 3 codes per list per day

2. **Access Control**
   - All operations check `ShoppingListUser` membership
   - Owners can't be removed (must transfer ownership first)
   - Viewers can only read, not modify

3. **WebSocket Authentication**
   - JWT token required on connect
   - Token refresh mechanism for long sessions
   - Auto-disconnect after 24h, require reconnect

4. **Data Privacy**
   - Email invites don't reveal list contents
   - Share codes are one-time use
   - Activity events are list-scoped, not globally visible

---

## Performance Considerations

1. **Database Queries**
   - Index on `shopping_list_items.due_at` for deadline sorting
   - Composite index on `shopping_list_events(list_id, sequence)` for sync
   - Limit event history to 1000 entries per list (auto-cleanup)

2. **Real-Time Sync**
   - Batch multiple rapid changes (debounce 100ms)
   - Delta sync only (sequence-based, not full refresh)
   - Presence updates throttled to 5s intervals

3. **Caching**
   - Cache member list in Redis (1h TTL)
   - Cache deadline calculations (invalidate on item change)
   - Widget state persisted locally (immediate render)

---

*Last updated: January 2026*
