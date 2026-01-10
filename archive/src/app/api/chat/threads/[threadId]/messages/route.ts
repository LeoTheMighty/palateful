import { NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getCurrentUser } from '@/lib/auth/session';
import { chatStream, type ChatMessage, type ToolContext } from '@/lib/ai';
import { generateTitlePrompt } from '@/lib/ai/prompts';
import { openai, DEFAULT_MODEL } from '@/lib/ai/client';

interface RouteParams {
  params: Promise<{ threadId: string }>;
}

// POST /api/chat/threads/[threadId]/messages - Send a message and get streaming response
export async function POST(request: NextRequest, { params }: RouteParams) {
  const user = await getCurrentUser();
  if (!user) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const { threadId } = await params;

  try {
    const body = await request.json();
    const { content } = body as { content: string };

    if (!content?.trim()) {
      return new Response(JSON.stringify({ error: 'Message content required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Verify thread ownership
    const thread = await prisma.thread.findFirst({
      where: { id: threadId, userId: user.id },
      include: {
        chats: {
          orderBy: { createdAt: 'asc' },
          select: {
            role: true,
            content: true,
            toolCalls: true,
            toolCallId: true,
            toolName: true,
          },
        },
      },
    });

    if (!thread) {
      return new Response(JSON.stringify({ error: 'Thread not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Save the user message
    const userChat = await prisma.chat.create({
      data: {
        threadId,
        role: 'user',
        content: content.trim(),
      },
    });

    // Generate title if this is the first message
    const shouldGenerateTitle = thread.chats.length === 0 && !thread.title;

    // Build conversation history
    const messages: ChatMessage[] = thread.chats.map((chat) => ({
      role: chat.role as ChatMessage['role'],
      content: chat.content,
      toolCalls: chat.toolCalls as unknown as ChatMessage['toolCalls'],
      toolCallId: chat.toolCallId || undefined,
      toolName: chat.toolName || undefined,
    }));

    // Add the new user message
    messages.push({
      role: 'user',
      content: content.trim(),
    });

    // Tool context for executors
    const context: ToolContext = {
      userId: user.id,
      threadId,
    };

    // Create a readable stream for SSE
    const encoder = new TextEncoder();
    let assistantContent = '';
    let assistantToolCalls: ChatMessage['toolCalls'] = undefined;

    const stream = new ReadableStream({
      async start(controller) {
        try {
          // Stream the chat response
          for await (const event of chatStream(messages, context)) {
            // Send SSE event
            const data = JSON.stringify(event);
            controller.enqueue(encoder.encode(`data: ${data}\n\n`));

            // Accumulate assistant content
            if (event.type === 'text') {
              assistantContent += event.content;
            }

            // Handle done event
            if (event.type === 'done') {
              // Save the assistant message
              await prisma.chat.create({
                data: {
                  threadId,
                  role: 'assistant',
                  content: assistantContent || null,
                  toolCalls: assistantToolCalls || undefined,
                  model: DEFAULT_MODEL,
                },
              });

              // Update thread timestamp
              await prisma.thread.update({
                where: { id: threadId },
                data: { updatedAt: new Date() },
              });

              // Generate title if needed
              if (shouldGenerateTitle) {
                try {
                  const titleResponse = await openai.chat.completions.create({
                    model: 'gpt-4o-mini',
                    messages: [
                      {
                        role: 'user',
                        content: generateTitlePrompt(content.trim()),
                      },
                    ],
                    max_tokens: 20,
                  });

                  const generatedTitle = titleResponse.choices[0]?.message?.content?.trim();
                  if (generatedTitle) {
                    await prisma.thread.update({
                      where: { id: threadId },
                      data: { title: generatedTitle },
                    });

                    // Send title update event
                    controller.enqueue(
                      encoder.encode(
                        `data: ${JSON.stringify({ type: 'title', title: generatedTitle })}\n\n`
                      )
                    );
                  }
                } catch (titleError) {
                  console.error('Failed to generate title:', titleError);
                }
              }
            }
          }

          controller.close();
        } catch (error) {
          console.error('Stream error:', error);
          const errorEvent = JSON.stringify({
            type: 'error',
            error: error instanceof Error ? error.message : 'Stream failed',
          });
          controller.enqueue(encoder.encode(`data: ${errorEvent}\n\n`));
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  } catch (error) {
    console.error('Failed to process message:', error);
    return new Response(JSON.stringify({ error: 'Failed to process message' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
