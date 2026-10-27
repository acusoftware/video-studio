create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  script text not null,
  voice text not null default 'tr-TR-EmelNeural',
  status text not null default 'queued' check (status in ('queued','rendering','done','error')),
  progress int not null default 0,
  video_url text,
  error text,
  created_at timestamptz not null default now()
);

-- Tabloya sadece sunucu (service role) erişir; RLS açık, policy yok.
alter table public.jobs enable row level security;

-- Herkese açık video klasörü (okuma herkese açık, yazma sadece service role)
insert into storage.buckets (id, name, public)
values ('videos', 'videos', true)
on conflict (id) do nothing;
