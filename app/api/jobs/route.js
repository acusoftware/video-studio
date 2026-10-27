import { NextResponse } from 'next/server';
import { db } from '@/lib/supabase';
import { MAX_CHARS } from '@/lib/limits';

export const dynamic = 'force-dynamic';

const env = (k) => (process.env[k] || '').trim();

export async function POST(req) {
  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Geçersiz istek' }, { status: 400 });
  }

  const { script = '', voice = 'tr-TR-EmelNeural', password = '' } = body;

  if (!env('APP_PASSWORD') || password.trim() !== env('APP_PASSWORD')) {
    return NextResponse.json({ error: 'Şifre yanlış' }, { status: 401 });
  }
  const text = String(script).trim();
  if (text.length < 10 || text.length > MAX_CHARS) {
    return NextResponse.json(
      { error: `Senaryo 10-${MAX_CHARS} karakter olmalı (şu an ${text.length})` },
      { status: 400 }
    );
  }
  if (!/^[a-z]{2}-[A-Z]{2}-[A-Za-z]+Neural$/.test(voice)) {
    return NextResponse.json({ error: 'Geçersiz ses' }, { status: 400 });
  }

  const supabase = db();
  const { data: job, error } = await supabase
    .from('jobs')
    .insert({ script: text, voice })
    .select('id')
    .single();
  if (error) {
    return NextResponse.json({ error: 'Veritabanı hatası: ' + error.message }, { status: 500 });
  }

  const repo = env('GITHUB_REPO');
  const branch = env('GITHUB_BRANCH') || 'main';
  const res = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows/render.yml/dispatches`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${env('GITHUB_DISPATCH_TOKEN')}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
        'User-Agent': 'video-studio',
      },
      body: JSON.stringify({ ref: branch, inputs: { job_id: job.id } }),
    }
  );

  if (!res.ok) {
    const msg = (await res.text()).slice(0, 300);
    const detail = `GitHub hatası ${res.status} (repo: [${repo}], dal: [${branch}]): ${msg}`;
    await supabase.from('jobs').update({ status: 'error', error: detail }).eq('id', job.id);
    return NextResponse.json({ error: detail }, { status: 502 });
  }

  return NextResponse.json({ id: job.id });
}
