import { NextResponse } from 'next/server';
import { db } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

export async function GET(_req, { params }) {
  const { id } = params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) {
    return NextResponse.json({ error: 'Geçersiz id' }, { status: 400 });
  }
  const { data, error } = await db()
    .from('jobs')
    .select('id,status,progress,video_url,error')
    .eq('id', id)
    .maybeSingle();
  if (error || !data) {
    return NextResponse.json({ error: 'Bulunamadı' }, { status: 404 });
  }
  return NextResponse.json(data);
}
