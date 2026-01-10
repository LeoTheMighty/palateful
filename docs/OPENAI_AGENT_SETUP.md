# OpenAI Agent Setup for Palateful

This document covers how to set up and use OpenAI's API for the Palateful AI chat agent.

## Overview

We use OpenAI's **Chat Completions API** with **function calling (tools)** to create an AI assistant that can:
- Search and browse recipes
- Suggest new recipes based on preferences
- Check what can be made with pantry contents
- Help import and manage recipes

## Setup

### 1. Install Dependencies

```bash
yarn add openai
```

### 2. Environment Variables

Add to `.env.local`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o  # or gpt-4o-mini for lower cost
```

### 3. Create OpenAI Client

```typescript
// src/lib/ai/client.ts
import OpenAI from 'openai';

export const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export const DEFAULT_MODEL = process.env.OPENAI_MODEL || 'gpt-4o-mini';
```

## Core Concepts

### Chat Completions with Tools

OpenAI's Chat Completions API accepts:
- **messages**: Array of conversation messages
- **tools**: Array of function definitions the model can call
- **tool_choice**: Control when/how tools are called

```typescript
const response = await openai.chat.completions.create({
  model: 'gpt-4o',
  messages: [
    { role: 'system', content: 'You are a helpful cooking assistant...' },
    { role: 'user', content: 'What can I make with chicken and rice?' }
  ],
  tools: [
    {
      type: 'function',
      function: {
        name: 'searchRecipes',
        description: 'Search for recipes by ingredients or keywords',
        parameters: {
          type: 'object',
          properties: {
            query: { type: 'string', description: 'Search query' },
            ingredients: {
              type: 'array',
              items: { type: 'string' },
              description: 'Required ingredients'
            }
          },
          required: ['query']
        }
      }
    }
  ]
});
```

### Tool Call Flow

1. **User sends message** → API receives conversation
2. **Model decides to call tool** → Returns `tool_calls` in response
3. **Execute tool** → Run the function with provided arguments
4. **Send tool result** → Add tool response to messages
5. **Model generates final response** → Natural language answer

```typescript
// Handling tool calls
if (response.choices[0].message.tool_calls) {
  const toolCalls = response.choices[0].message.tool_calls;

  // Add assistant message with tool calls
  messages.push(response.choices[0].message);

  // Execute each tool and add results
  for (const toolCall of toolCalls) {
    const result = await executeToolCall(toolCall);
    messages.push({
      role: 'tool',
      tool_call_id: toolCall.id,
      content: JSON.stringify(result)
    });
  }

  // Get final response
  const finalResponse = await openai.chat.completions.create({
    model: 'gpt-4o',
    messages,
    tools
  });
}
```

### Streaming Responses

For better UX, stream responses to show text as it's generated:

```typescript
const stream = await openai.chat.completions.create({
  model: 'gpt-4o',
  messages,
  tools,
  stream: true
});

for await (const chunk of stream) {
  const delta = chunk.choices[0]?.delta;

  if (delta?.content) {
    // Text content - send to client
    yield { type: 'text', content: delta.content };
  }

  if (delta?.tool_calls) {
    // Tool call being built up
    yield { type: 'tool_call', data: delta.tool_calls };
  }
}
```

## Tool Definitions for Palateful

### Recipe Tools

```typescript
// src/lib/ai/tools/recipes.ts

export const recipeTools = [
  {
    type: 'function',
    function: {
      name: 'searchRecipes',
      description: 'Search for recipes by name, ingredients, or description',
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Search term (recipe name or keywords)'
          },
          ingredients: {
            type: 'array',
            items: { type: 'string' },
            description: 'Filter by required ingredients'
          },
          category: {
            type: 'string',
            description: 'Filter by category (breakfast, dinner, dessert, etc.)'
          },
          maxCookTime: {
            type: 'number',
            description: 'Maximum cooking time in minutes'
          }
        }
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'listRecipes',
      description: 'Get a list of recipes with optional filters',
      parameters: {
        type: 'object',
        properties: {
          limit: { type: 'number', description: 'Max results (default 10)' },
          offset: { type: 'number', description: 'Pagination offset' },
          sortBy: {
            type: 'string',
            enum: ['name', 'createdAt', 'cookTime', 'rating'],
            description: 'Sort field'
          },
          sortOrder: {
            type: 'string',
            enum: ['asc', 'desc'],
            description: 'Sort direction'
          }
        }
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'getRecipeDetails',
      description: 'Get full details of a specific recipe including ingredients and instructions',
      parameters: {
        type: 'object',
        properties: {
          recipeId: { type: 'string', description: 'The recipe ID' }
        },
        required: ['recipeId']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'suggestRecipe',
      description: 'Generate a new recipe suggestion based on preferences or available ingredients',
      parameters: {
        type: 'object',
        properties: {
          preferences: {
            type: 'string',
            description: 'User preferences or constraints (cuisine, dietary, etc.)'
          },
          availableIngredients: {
            type: 'array',
            items: { type: 'string' },
            description: 'Ingredients the user has available'
          },
          style: {
            type: 'string',
            enum: ['quick', 'elaborate', 'healthy', 'comfort'],
            description: 'Recipe style preference'
          }
        }
      }
    }
  }
];
```

### Pantry Tools

```typescript
// src/lib/ai/tools/pantry.ts

export const pantryTools = [
  {
    type: 'function',
    function: {
      name: 'getPantryContents',
      description: 'Get list of ingredients currently in the user\'s pantry',
      parameters: {
        type: 'object',
        properties: {
          category: {
            type: 'string',
            description: 'Filter by category (produce, dairy, protein, etc.)'
          }
        }
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'checkRecipeFeasibility',
      description: 'Check if a recipe can be made with current pantry contents',
      parameters: {
        type: 'object',
        properties: {
          recipeId: { type: 'string', description: 'Recipe to check' }
        },
        required: ['recipeId']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'addToPantry',
      description: 'Add an ingredient to the user\'s pantry',
      parameters: {
        type: 'object',
        properties: {
          ingredientName: { type: 'string', description: 'Name of ingredient' },
          quantity: { type: 'number', description: 'Amount' },
          unit: { type: 'string', description: 'Unit (cups, lbs, etc.)' }
        },
        required: ['ingredientName', 'quantity', 'unit']
      }
    }
  }
];
```

## System Prompt

```typescript
// src/lib/ai/prompts.ts

export const SYSTEM_PROMPT = `You are Palateful, a friendly and knowledgeable cooking assistant.

Your capabilities:
- Search and browse the user's recipe collection
- Suggest new recipes based on preferences or available ingredients
- Check what recipes can be made with pantry contents
- Help organize and manage recipes

Guidelines:
- Be conversational and helpful
- When suggesting recipes, consider dietary preferences mentioned
- Use tools to access real data rather than making up recipes
- If you don't have enough information, ask clarifying questions
- Format recipes nicely when displaying them

When the user asks about recipes, always use the appropriate tool to get accurate data from their collection.`;
```

## API Route Implementation

```typescript
// src/app/api/chat/route.ts

import { NextRequest } from 'next/server';
import { openai, DEFAULT_MODEL } from '@/lib/ai/client';
import { recipeTools, pantryTools } from '@/lib/ai/tools';
import { executeToolCall } from '@/lib/ai/executor';
import { SYSTEM_PROMPT } from '@/lib/ai/prompts';

export async function POST(request: NextRequest) {
  const { messages, threadId } = await request.json();

  // Prepend system message
  const fullMessages = [
    { role: 'system', content: SYSTEM_PROMPT },
    ...messages
  ];

  // Create streaming response
  const stream = await openai.chat.completions.create({
    model: DEFAULT_MODEL,
    messages: fullMessages,
    tools: [...recipeTools, ...pantryTools],
    stream: true
  });

  // Return as Server-Sent Events
  const encoder = new TextEncoder();
  const readable = new ReadableStream({
    async start(controller) {
      for await (const chunk of stream) {
        const data = JSON.stringify(chunk);
        controller.enqueue(encoder.encode(`data: ${data}\n\n`));
      }
      controller.enqueue(encoder.encode('data: [DONE]\n\n'));
      controller.close();
    }
  });

  return new Response(readable, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    }
  });
}
```

## Frontend Streaming Hook

```typescript
// src/hooks/useChat.ts

import { useState, useCallback } from 'react';

interface Message {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
}

export function useChat(threadId?: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(async (content: string) => {
    const userMessage = { role: 'user' as const, content };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [...messages, userMessage],
          threadId
        })
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ') && line !== 'data: [DONE]') {
            const data = JSON.parse(line.slice(6));
            const content = data.choices?.[0]?.delta?.content;
            if (content) {
              assistantMessage += content;
              setMessages(prev => {
                const updated = [...prev];
                const lastIdx = updated.length - 1;
                if (updated[lastIdx]?.role === 'assistant') {
                  updated[lastIdx] = { role: 'assistant', content: assistantMessage };
                } else {
                  updated.push({ role: 'assistant', content: assistantMessage });
                }
                return updated;
              });
            }
          }
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, [messages, threadId]);

  return { messages, sendMessage, isLoading };
}
```

## Token Usage & Cost Tracking

Store usage in the Chat model for cost analysis:

```typescript
// After getting a response
const usage = response.usage;
await prisma.chat.update({
  where: { id: chatId },
  data: {
    promptTokens: usage?.prompt_tokens,
    completionTokens: usage?.completion_tokens,
    model: DEFAULT_MODEL
  }
});
```

### Cost Estimation (as of late 2024)

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |

## Next Steps

1. Install OpenAI SDK: `yarn add openai`
2. Create `src/lib/ai/` directory structure
3. Implement tool executors that call our existing lib functions
4. Create chat API route with streaming
5. Build chat UI component
6. Add thread management (create, list, delete)

## References

- [OpenAI Chat Completions API](https://platform.openai.com/docs/guides/chat-completions)
- [Function Calling Guide](https://platform.openai.com/docs/guides/function-calling)
- [Streaming Responses](https://platform.openai.com/docs/api-reference/streaming)
- [Best Practices](https://platform.openai.com/docs/guides/production-best-practices)
