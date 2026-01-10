import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getCurrentUser } from '@/lib/auth/session';

// GET /api/chat/threads - List all threads for current user
export async function GET() {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const threads = await prisma.thread.findMany({
      where: { userId: user.id },
      orderBy: { updatedAt: 'desc' },
      select: {
        id: true,
        title: true,
        createdAt: true,
        updatedAt: true,
        _count: {
          select: { chats: true },
        },
      },
    });

    return NextResponse.json({
      threads: threads.map((t) => ({
        id: t.id,
        title: t.title,
        createdAt: t.createdAt,
        updatedAt: t.updatedAt,
        messageCount: t._count.chats,
      })),
    });
  } catch (error) {
    console.error('Failed to list threads:', error);
    return NextResponse.json({ error: 'Failed to list threads' }, { status: 500 });
  }
}

// POST /api/chat/threads - Create a new thread
export async function POST(request: NextRequest) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json().catch(() => ({}));
    const { title } = body as { title?: string };

    const thread = await prisma.thread.create({
      data: {
        userId: user.id,
        title: title || null,
      },
      select: {
        id: true,
        title: true,
        createdAt: true,
        updatedAt: true,
      },
    });

    return NextResponse.json({ thread }, { status: 201 });
  } catch (error) {
    console.error('Failed to create thread:', error);
    return NextResponse.json({ error: 'Failed to create thread' }, { status: 500 });
  }
}
