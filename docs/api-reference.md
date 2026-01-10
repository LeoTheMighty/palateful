# Palateful API Reference

## Overview

RESTful API built with Next.js API Routes. Authentication via Auth0.

**Base URL:** `https://api.palateful.app` (production) or `http://localhost:3000` (development)

---

## Authentication

### Auth0 Integration

All protected endpoints require a valid Auth0 JWT token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Auth Endpoints

#### `GET/POST /api/auth/[auth0]`

Handles all Auth0 authentication flows (login, callback, logout).

**Flows:**
- `/api/auth/login` - Initiate login
- `/api/auth/callback` - OAuth callback
- `/api/auth/logout` - Logout
- `/api/auth/me` - Get current user info

---

## User Endpoints

### Complete Onboarding

Mark user onboarding as complete.

```
POST /api/user/complete-onboarding
```

**Authentication:** Required

**Request:** Empty body

**Response:**
```json
{
  "success": true
}
```

**Errors:**
- `401` - Unauthorized

---

## Ingredient Endpoints

### Search Ingredients

Search for ingredients with fuzzy and semantic matching.

```
GET /api/ingredients/search
```

**Authentication:** Not required

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | Yes | - | Search query |
| `fuzzyThreshold` | number | No | 0.3 | Minimum fuzzy similarity |
| `semanticThreshold` | number | No | 0.7 | Minimum semantic similarity |
| `limit` | number | No | 10 | Max results |
| `semantic` | boolean | No | true | Include semantic search |

**Response:**
```json
{
  "action": "matched",
  "ingredient": {
    "id": "clm123...",
    "canonicalName": "tomato",
    "category": "produce",
    "matchType": "exact",
    "similarity": 1.0
  }
}
```

**Action Values:**
- `matched` - Single confident match found
- `confirm` - Multiple suggestions, user should confirm
- `create_new` - No matches, suggest creating new ingredient

---

### Create Ingredient

Create a new user-submitted ingredient.

```
POST /api/ingredients/search
```

**Authentication:** Not required (but userId required in body)

**Request:**
```json
{
  "name": "heirloom tomato",
  "userId": "user_123",
  "category": "produce",
  "aliases": ["heirloom", "heritage tomato"]
}
```

**Response:**
```json
{
  "id": "clm789...",
  "canonicalName": "heirloom tomato"
}
```

**Status:** `201 Created`

---

## Recipe Endpoints

### Check Recipe Feasibility

Check if a recipe can be made with current pantry contents.

```
GET /api/recipes/[id]/feasibility
```

**Authentication:** Not required (pantryId in query)

**Path Parameters:**
- `id` - Recipe ID

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pantryId` | string | Yes | - | Pantry to check against |
| `scale` | number | No | 1 | Recipe scale factor |

**Response:**
```json
{
  "recipeId": "clm123...",
  "recipeName": "Lemon Garlic Chicken",
  "canMake": false,
  "canMakeWithSubstitutes": true,
  "requirements": [
    {
      "ingredientId": "ing_001",
      "ingredientName": "chicken breast",
      "needed": 907.18,
      "have": 907.18,
      "unit": "g",
      "status": "have",
      "shortfall": 0,
      "isOptional": false
    }
  ],
  "missingWithSubstitutes": [
    {
      "ingredientId": "ing_002",
      "ingredientName": "lemon",
      "needed": 2,
      "have": 0,
      "unit": "count",
      "status": "missing",
      "shortfall": 2,
      "isOptional": false,
      "substitutes": [
        {
          "substituteId": "ing_003",
          "substituteName": "lime",
          "quality": "perfect",
          "ratio": 1.0,
          "notes": null,
          "haveAmount": 3,
          "canFullySubstitute": true
        }
      ]
    }
  ],
  "shoppingList": []
}
```

**Errors:**
- `400` - Missing pantryId
- `404` - Recipe not found

---

### Cook Recipe

Execute cooking a recipe, deducting ingredients from pantry.

```
POST /api/recipes/[id]/cook
```

**Authentication:** Not required (pantryId in body)

**Path Parameters:**
- `id` - Recipe ID

**Request:**
```json
{
  "pantryId": "pantry_123",
  "scale": 1.5,
  "substitutes": [
    {
      "ingredientId": "ing_002",
      "substituteId": "ing_003",
      "quantity": 3
    }
  ],
  "notes": "Added extra garlic"
}
```

**Response:**
```json
{
  "success": true,
  "deducted": [
    {
      "ingredient": "chicken breast",
      "amountUsed": 1360.77,
      "amountRemaining": 0
    },
    {
      "ingredient": "lime",
      "amountUsed": 3,
      "amountRemaining": 0
    }
  ],
  "cookingLogId": "log_456"
}
```

**Errors:**
- `400` - Missing pantryId or insufficient ingredients
- `404` - Recipe not found

---

## Chat Endpoints

### List Threads

Get all chat threads for the current user.

```
GET /api/chat/threads
```

**Authentication:** Required

**Response:**
```json
{
  "threads": [
    {
      "id": "thread_123",
      "title": "Finding dinner recipes",
      "createdAt": "2025-01-08T12:00:00Z",
      "updatedAt": "2025-01-08T12:30:00Z",
      "messageCount": 5
    }
  ]
}
```

---

### Create Thread

Create a new chat thread.

```
POST /api/chat/threads
```

**Authentication:** Required

**Request:**
```json
{
  "title": "Meal planning"
}
```

`title` is optional - will be auto-generated from first message.

**Response:**
```json
{
  "thread": {
    "id": "thread_456",
    "title": null,
    "createdAt": "2025-01-08T12:00:00Z",
    "updatedAt": "2025-01-08T12:00:00Z"
  }
}
```

**Status:** `201 Created`

---

### Get Thread

Get a specific thread with all messages.

```
GET /api/chat/threads/[threadId]
```

**Authentication:** Required

**Path Parameters:**
- `threadId` - Thread ID

**Response:**
```json
{
  "thread": {
    "id": "thread_123",
    "title": "Finding dinner recipes",
    "createdAt": "2025-01-08T12:00:00Z",
    "updatedAt": "2025-01-08T12:30:00Z",
    "chats": [
      {
        "id": "chat_001",
        "role": "user",
        "content": "What can I make for dinner?",
        "createdAt": "2025-01-08T12:00:00Z",
        "toolCalls": null,
        "toolCallId": null,
        "toolName": null
      },
      {
        "id": "chat_002",
        "role": "assistant",
        "content": "Let me check your pantry...",
        "createdAt": "2025-01-08T12:00:05Z",
        "toolCalls": [
          {
            "id": "call_123",
            "type": "function",
            "function": {
              "name": "getPantryContents",
              "arguments": "{}"
            }
          }
        ],
        "toolCallId": null,
        "toolName": null
      }
    ]
  }
}
```

**Errors:**
- `404` - Thread not found

---

### Update Thread

Update thread properties (e.g., title).

```
PATCH /api/chat/threads/[threadId]
```

**Authentication:** Required

**Path Parameters:**
- `threadId` - Thread ID

**Request:**
```json
{
  "title": "Weekly meal planning"
}
```

**Response:**
```json
{
  "thread": {
    "id": "thread_123",
    "title": "Weekly meal planning",
    "updatedAt": "2025-01-08T12:35:00Z"
  }
}
```

**Errors:**
- `404` - Thread not found

---

### Delete Thread

Delete a thread and all its messages.

```
DELETE /api/chat/threads/[threadId]
```

**Authentication:** Required

**Path Parameters:**
- `threadId` - Thread ID

**Response:**
```json
{
  "success": true
}
```

**Errors:**
- `404` - Thread not found

---

### Send Message (Streaming)

Send a message and receive a streaming response via Server-Sent Events.

```
POST /api/chat/threads/[threadId]/messages
```

**Authentication:** Required

**Path Parameters:**
- `threadId` - Thread ID

**Request:**
```json
{
  "content": "What's in my pantry?"
}
```

**Response:** Server-Sent Events stream

**Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**Event Types:**

| Event Type | Data | Description |
|------------|------|-------------|
| `text` | `{"type":"text","content":"..."}` | Partial text response |
| `tool_call_start` | `{"type":"tool_call_start","toolCall":{"id":"...","name":"..."}}` | Tool invocation started |
| `tool_call_args` | `{"type":"tool_call_args","toolCallId":"...","args":"..."}` | Incremental tool arguments |
| `tool_call_complete` | `{"type":"tool_call_complete","toolCallId":"..."}` | Tool call arguments complete |
| `tool_result` | `{"type":"tool_result","toolCallId":"...","result":{...}}` | Tool execution result |
| `done` | `{"type":"done"}` | Response complete |
| `title` | `{"type":"title","title":"..."}` | Auto-generated thread title |
| `error` | `{"type":"error","error":"..."}` | Error occurred |

**Example Stream:**
```
data: {"type":"tool_call_start","toolCall":{"id":"call_123","name":"getPantryContents"}}

data: {"type":"tool_call_args","toolCallId":"call_123","args":"{}"}

data: {"type":"tool_call_complete","toolCallId":"call_123"}

data: {"type":"tool_result","toolCallId":"call_123","result":{"success":true,"data":{"totalItems":15}}}

data: {"type":"text","content":"You have "}

data: {"type":"text","content":"15 items "}

data: {"type":"text","content":"in your pantry."}

data: {"type":"done"}

data: {"type":"title","title":"Pantry inventory check"}
```

**Errors:**
- `400` - Message content required
- `404` - Thread not found

---

## Error Response Format

All endpoints return errors in this format:

```json
{
  "error": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (missing/invalid parameters) |
| 401 | Unauthorized (missing/invalid token) |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Rate Limiting

Currently no rate limiting implemented. Planned for production:

| Endpoint Type | Limit |
|---------------|-------|
| Chat (AI) | 20 requests/minute |
| Search | 100 requests/minute |
| CRUD | 200 requests/minute |

---

## CORS

Allowed origins configured via `CORS_ORIGINS` environment variable.

Default (development):
- `http://localhost:3000`

---

## Versioning

API is currently unversioned. Future versions will use path prefix:
- `/api/v1/...`
- `/api/v2/...`

---

## SDKs & Examples

### JavaScript/TypeScript

```typescript
// Using fetch for SSE
const response = await fetch(`/api/chat/threads/${threadId}/messages`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ content: 'Hello!' })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const text = decoder.decode(value);
  const lines = text.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      console.log(data);
    }
  }
}
```

### Python

```python
import requests
import sseclient

url = f"{BASE_URL}/api/chat/threads/{thread_id}/messages"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.post(url, json={"content": "Hello!"}, headers=headers, stream=True)
client = sseclient.SSEClient(response)

for event in client.events():
    data = json.loads(event.data)
    print(data)
```

### cURL

```bash
# Create thread
curl -X POST http://localhost:3000/api/chat/threads \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Send message (SSE)
curl -N http://localhost:3000/api/chat/threads/$THREAD_ID/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "What can I make for dinner?"}'
```
