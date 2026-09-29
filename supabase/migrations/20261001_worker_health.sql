begin;
create table public.media_worker_health (
  id integer primary key check (id=1),
  last_seen timestamptz not null default now()
);
alter table public.media_worker_health enable row level security;
revoke all on public.media_worker_health from anon, authenticated;
grant all on public.media_worker_health to service_role;
commit;
