begin;
alter table public.scans add column if not exists input_sha256 text;
create unique index if not exists analysis_results_one_per_scan on public.analysis_results(scan_id);
create index if not exists scans_owner_created on public.scans(user_id, created_at desc);
alter table public.scans add constraint scores_in_range check (
  ai_generated_probability between 0 and 1 and ai_edited_probability between 0 and 1
  and traditional_edit_probability between 0 and 1 and authentic_probability between 0 and 1
  and confidence between 0 and 1) not valid;

create or replace function public.save_scan_atomic(
  p_scan_id uuid, p_user_id uuid, p_file_type text, p_filename text,
  p_result jsonb, p_input_sha256 text
) returns uuid language plpgsql security invoker set search_path = '' as $$
declare existing public.scans;
begin
  if p_user_id is null or p_input_sha256 is null or p_input_sha256 !~ '^[a-f0-9]{64}$' then
    raise exception 'Invalid owner or content digest';
  end if;
  if p_result is null then raise exception 'Missing report'; end if;
  if octet_length(p_result::text) > 524288 then raise exception 'Report too large'; end if;
  perform pg_advisory_xact_lock(hashtextextended(p_user_id::text, 0));
  select * into existing from public.scans where id = p_scan_id;
  if found then
    if existing.user_id is distinct from p_user_id
       or existing.input_sha256 is distinct from p_input_sha256 then
      raise exception 'Idempotency conflict';
    end if;
    return existing.id;
  end if;
  if (select count(*) from public.scans where user_id = p_user_id
      and created_at > now() - interval '1 day') >= 50 then
    raise exception 'Daily report quota reached';
  end if;
  insert into public.scans (id, user_id, file_type, filename, input_sha256, verdict,
      ai_generated_probability, ai_edited_probability, traditional_edit_probability,
      authentic_probability, confidence)
    values (p_scan_id, p_user_id, p_file_type, left(p_filename, 255), p_input_sha256,
      p_result->>'final_verdict', (p_result->>'ai_generated_probability')::float,
      (p_result->>'ai_edited_probability')::float, (p_result->>'traditional_edit_probability')::float,
      (p_result->>'authentic_probability')::float, (p_result->>'confidence')::float);
  insert into public.analysis_results(scan_id, result_json) values (p_scan_id, p_result);
  return p_scan_id;
end;
$$;
revoke all on function public.save_scan_atomic(uuid,uuid,text,text,jsonb,text) from public, anon, authenticated;
grant execute on function public.save_scan_atomic(uuid,uuid,text,text,jsonb,text) to service_role;

-- Explicit operator maintenance command. Never run automatically against old data.
create or replace function public.prune_expired_reports(p_before timestamptz)
returns bigint language plpgsql security invoker set search_path = '' as $$
declare removed bigint;
begin
  if p_before is null or p_before > now() - interval '30 days' then raise exception 'Minimum retention is 30 days'; end if;
  delete from public.scans where created_at < p_before;
  get diagnostics removed = row_count;
  return removed;
end;
$$;
revoke all on function public.prune_expired_reports(timestamptz) from public, anon, authenticated;
grant execute on function public.prune_expired_reports(timestamptz) to service_role;
commit;
