-- Forward-only admission limits. Does not delete existing jobs or reports.
begin;
create function public.enforce_media_job_budget() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
  -- Called by the coordinator while its global advisory lock is held.
  if pg_database_size(current_database()) >= 400000000 then
    raise exception 'Database quota reached';
  end if;
  if (select count(*) from public.media_jobs where created_at > now()-interval '1 day') >= 100 then
    raise exception 'Daily global job quota reached';
  end if;
  -- Conservative transfer reservation, including failed/abandoned uploads.
  -- Replayed signed download URLs can still consume additional provider egress.
  if (select coalesce(sum(byte_size*2 + case when kind='clean' then 100000000 else 0 end),0)
      from public.media_jobs where created_at >= date_trunc('month',now()))
      + new.byte_size*2 + (case when new.kind='clean' then 100000000 else 0 end) > 2000000000 then
    raise exception 'Monthly transfer quota reached';
  end if;
  return new;
end;
$$;
revoke all on function public.enforce_media_job_budget() from public, anon, authenticated;
grant execute on function public.enforce_media_job_budget() to service_role;
create trigger media_job_budget before insert on public.media_jobs
for each row execute function public.enforce_media_job_budget();
commit;
