-- MediaTruth Database Schema
-- Run this in your Supabase SQL editor

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- ─── users (mirrors auth.users via trigger) ─────────────────────────────────
create table if not exists public.users (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text,
  created_at  timestamptz default now()
);

-- ─── scans ──────────────────────────────────────────────────────────────────
create table if not exists public.scans (
  id                          uuid primary key default uuid_generate_v4(),
  user_id                     uuid references public.users(id) on delete set null,
  file_type                   text not null check (file_type in ('image', 'video')),
  filename                    text,
  verdict                     text,
  ai_generated_probability    float,
  ai_edited_probability       float,
  traditional_edit_probability float,
  authentic_probability       float,
  confidence                  float,
  created_at                  timestamptz default now()
);

create index if not exists idx_scans_user_id    on public.scans(user_id);
create index if not exists idx_scans_created_at on public.scans(created_at desc);

-- ─── analysis_results ────────────────────────────────────────────────────────
create table if not exists public.analysis_results (
  id          uuid primary key default uuid_generate_v4(),
  scan_id     uuid not null references public.scans(id) on delete cascade,
  result_json jsonb not null,
  created_at  timestamptz default now()
);

create index if not exists idx_results_scan_id on public.analysis_results(scan_id);

-- ─── Row-level security ──────────────────────────────────────────────────────
alter table public.scans           enable row level security;
alter table public.analysis_results enable row level security;
alter table public.users enable row level security;

create policy "users_read_own_profile"
  on public.users for select to authenticated
  using (id = auth.uid());

-- ─── SELECT policies ─────────────────────────────────────────────────────────
-- Users can read only their own scans; ownerless scans remain private
create policy "users_read_own_scans"
  on public.scans for select to authenticated
  using (user_id = auth.uid());

create policy "users_read_own_results"
  on public.analysis_results for select to authenticated
  using (
    scan_id in (
      select id from public.scans
      where user_id = auth.uid()
    )
  );

-- ─── INSERT policies (REMAINING-006) ────────────────────────────────────────
-- Only the service_role (backend) should insert scans.
-- service_role bypasses RLS entirely, but these policies provide defense-in-depth
-- if the anon key is ever accidentally used server-side.

-- Backend service role bypasses RLS. Browser clients cannot create forged results.
revoke insert, update on public.users, public.scans, public.analysis_results from anon, authenticated;

-- ─── UPDATE policies (REMAINING-006) ────────────────────────────────────────
-- Scans and results are immutable — nobody can modify them after creation.
-- This prevents tampering with forensic analysis records.

create policy "no_user_updates_scans"
  on public.scans for update
  using (false);

create policy "no_user_updates_results"
  on public.analysis_results for update
  using (false);

-- ─── DELETE policies ─────────────────────────────────────────────────────────
-- Only the scan owner can delete their own scans (cascades to analysis_results)
create policy "users_delete_own_scans"
  on public.scans for delete
  using (user_id = auth.uid());

-- ─── Auto-create user profile on signup ─────────────────────────────────────
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.users (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

revoke execute on function public.handle_new_user() from public, anon, authenticated;
