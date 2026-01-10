import { NextRequest, NextResponse } from 'next/server';
import { checkRecipeFeasibility } from '@/lib/recipes/feasibility';

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const pantryId = request.nextUrl.searchParams.get('pantryId');
  const scale = parseFloat(request.nextUrl.searchParams.get('scale') || '1');

  if (!pantryId) {
    return NextResponse.json({ error: 'pantryId required' }, { status: 400 });
  }

  try {
    const feasibility = await checkRecipeFeasibility(id, pantryId, scale);
    return NextResponse.json(feasibility);
  } catch (error) {
    console.error('Feasibility check error:', error);
    if (error instanceof Error && error.message === 'Recipe not found') {
      return NextResponse.json({ error: 'Recipe not found' }, { status: 404 });
    }
    return NextResponse.json({ error: 'Failed to check feasibility' }, { status: 500 });
  }
}
