import { NextRequest, NextResponse } from 'next/server';
import { cookRecipe } from '@/lib/recipes/cooking';

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  try {
    const { pantryId, scale, substitutes, notes } = await request.json();

    if (!pantryId) {
      return NextResponse.json({ error: 'pantryId required' }, { status: 400 });
    }

    const result = await cookRecipe(id, pantryId, { scale, substitutes, notes });

    if (!result.success) {
      return NextResponse.json({ error: result.error }, { status: 400 });
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('Cook recipe error:', error);
    return NextResponse.json({ error: 'Failed to cook recipe' }, { status: 500 });
  }
}
