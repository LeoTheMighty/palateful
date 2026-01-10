import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getCurrentUser } from '@/lib/auth/session';

interface RouteParams {
  params: Promise<{ threadId: string }>;
}

// GET /api/chat/threads/[threadId] - Get a specific thread with messages
export async function GET(request: NextRequest, { params }: RouteParams) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { threadId } = await params;

  try {
    const thread = await prisma.thread.findFirst({
      where: {
        id: threadId,
        userId: user.id,
      },
      include: {
        chats: {
          orderBy: { createdAt: 'asc' },
          select: {
            id: true,
            role: true,
            content: true,
            createdAt: true,
            toolCalls: true,
            toolCallId: true,
            toolName: true,
          },
        },
      },
    });

    if (!thread) {
      return NextResponse.json({ error: 'Thread not found' }, { status: 404 });
    }

    return NextResponse.json({ thread });
  } catch (error) {
    console.error('Failed to get thread:', error);
    return NextResponse.json({ error: 'Failed to get thread' }, { status: 500 });
  }
}

// PATCH /api/chat/threads/[threadId] - Update thread (e.g., title)
export async function PATCH(request: NextRequest, { params }: RouteParams) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { threadId } = await params;

  try {
    const body = await request.json();
    const { title } = body as { title?: string };

    // Verify ownership
    const existing = await prisma.thread.findFirst({
      where: { id: threadId, userId: user.id },
    });

    if (!existing) {
      return NextResponse.json({ error: 'Thread not found' }, { status: 404 });
    }

    const thread = await prisma.thread.update({
      where: { id: threadId },
      data: { title },
      select: {
        id: true,
        title: true,
        updatedAt: true,
      },
    });

    return NextResponse.json({ thread });
  } catch (error) {
    console.error('Failed to update thread:', error);
    return NextResponse.json({ error: 'Failed to update thread' }, { status: 500 });
  }
}

// DELETE /api/chat/threads/[threadId] - Delete a thread
export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { threadId } = await params;

  try {
    // Verify ownership
    const existing = await prisma.thread.findFirst({
      where: { id: threadId, userId: user.id },
    });

    if (!existing) {
      return NextResponse.json({ error: 'Thread not found' }, { status: 404 });
    }

    await prisma.thread.delete({
      where: { id: threadId },
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Failed to delete thread:', error);
    return NextResponse.json({ error: 'Failed to delete thread' }, { status: 500 });
  }
}
