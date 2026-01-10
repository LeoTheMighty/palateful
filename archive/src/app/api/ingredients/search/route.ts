import { NextRequest, NextResponse } from 'next/server';
import { searchIngredients, createUserIngredient } from '@/lib/ingredients/search';

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const query = params.get('q');

  if (!query) {
    return NextResponse.json({ error: 'Query required' }, { status: 400 });
  }

  try {
    const result = await searchIngredients(query, {
      fuzzyThreshold: parseFloat(params.get('fuzzyThreshold') || '0.3'),
      semanticThreshold: parseFloat(params.get('semanticThreshold') || '0.7'),
      limit: parseInt(params.get('limit') || '10'),
      includeSemantic: params.get('semantic') !== 'false',
    });

    return NextResponse.json(result);
  } catch (error) {
    console.error('Ingredient search error:', error);
    return NextResponse.json({ error: 'Search failed' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const { name, userId, category, aliases } = await request.json();

    if (!name || !userId) {
      return NextResponse.json({ error: 'name and userId required' }, { status: 400 });
    }

    const result = await createUserIngredient(name, userId, { category, aliases });
    return NextResponse.json(result, { status: 201 });
  } catch (error) {
    console.error('Create ingredient error:', error);
    return NextResponse.json({ error: 'Failed to create ingredient' }, { status: 500 });
  }
}
