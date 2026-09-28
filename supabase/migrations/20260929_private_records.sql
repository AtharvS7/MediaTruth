-- Apply after schema.sql. Non-destructive: ownerless records stay stored but private.
begin;

alter table public.users enable row level security;
drop policy if exists users_read_own_profile on public.users;
create policy users_read_own_profile on public.users for select to authenticated
  using (id = auth.uid());

drop policy if exists users_read_own_scans on public.scans;
create policy users_read_own_scans on public.scans for select to authenticated
  using (user_id = auth.uid());

drop policy if exists users_read_own_results on public.analysis_results;
create policy users_read_own_results on public.analysis_results for select to authenticated
  using (exists (select 1 from public.scans s
    where s.id = scan_id and s.user_id = auth.uid()));

-- Service-role requests bypass RLS; unrestricted INSERT policies allow forged
-- records from browser clients and are not needed for backend writes.
drop policy if exists service_insert_scans on public.scans;
drop policy if exists service_insert_results on public.analysis_results;
revoke insert, update on public.users, public.scans, public.analysis_results from anon, authenticated;

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.users (id, email) values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;
commit;
