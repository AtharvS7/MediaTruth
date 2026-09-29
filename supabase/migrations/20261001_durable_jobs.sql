-- Additive migration. Rollback: disable JOB_BACKEND=supabase; retain private rows.
begin;
create table public.media_jobs (
  id uuid primary key default gen_random_uuid(),
  -- Retain cleanup records after account deletion; API always verifies live auth.
  owner uuid not null,
  kind text not null check (kind in ('image','video','clean')),
  filename text not null,
  input_sha256 text not null check (input_sha256 ~ '^[a-f0-9]{64}$'),
  byte_size bigint not null check (byte_size between 1 and 50000000),
  idempotency_key uuid not null,
  status text not null default 'uploading' check (status in
    ('uploading','queued','running','completed','failed','cancelled')),
  stage text not null default 'uploading',
  attempts integer not null default 0,
  lease uuid,
  lease_until timestamptz,
  cancel_requested boolean not null default false,
  error text,
  result jsonb,
  input_deleted boolean not null default false,
  output_deleted boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner,idempotency_key)
);
create index media_jobs_status_created on public.media_jobs(status,created_at);
alter table public.media_jobs enable row level security;
revoke all on public.media_jobs from anon, authenticated;
grant all on public.media_jobs to service_role;

-- Service-only coordinator. One global lock is intentional for a three-job queue.
create function public.media_job_action(p_action text, p_args jsonb default '{}')
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare j public.media_jobs; v_id uuid; v_owner uuid; v_lease uuid;
begin
  perform pg_advisory_xact_lock(724001);
  v_id := (p_args->>'id')::uuid;
  v_owner := (p_args->>'owner')::uuid;
  v_lease := (p_args->>'lease')::uuid;
  if p_action = 'reserve' then
    select * into j from public.media_jobs where owner=v_owner
      and idempotency_key=(p_args->>'idempotency_key')::uuid;
    if found then
      if j.input_sha256 <> p_args->>'input_sha256' or j.kind <> p_args->>'kind'
         or j.byte_size <> (p_args->>'byte_size')::bigint then
        raise exception 'Idempotency conflict';
      end if;
      return to_jsonb(j);
    end if;
    if (select count(*) from public.media_jobs where status in ('uploading','queued','running')) >= 3
       or exists(select 1 from public.media_jobs where owner=v_owner
                 and status in ('uploading','queued','running')) then
      raise exception 'Queue full';
    end if;
    if (select count(*) from public.media_jobs where owner=v_owner
        and created_at > now()-interval '1 day') >= 50 then
      raise exception 'Daily job quota reached';
    end if;
    -- Reserve room for input plus a maximum-size export; leave free-tier headroom.
    if (select coalesce(sum(case when not input_deleted then byte_size else 0 end
           + case when kind='clean' and not output_deleted then 50000000 else 0 end),0)
        from public.media_jobs) + (p_args->>'byte_size')::bigint + 50000000 > 500000000 then
      raise exception 'Storage quota reached';
    end if;
    insert into public.media_jobs(owner,kind,filename,input_sha256,byte_size,idempotency_key)
      values(v_owner,p_args->>'kind',left(p_args->>'filename',255),p_args->>'input_sha256',
             (p_args->>'byte_size')::bigint,(p_args->>'idempotency_key')::uuid) returning * into j;
    return to_jsonb(j);
  elsif p_action = 'claim' then
    update public.media_jobs set status=case when cancel_requested then 'cancelled'
      when attempts < 2 then 'queued' else 'failed' end,
      stage='recovering', lease=null, lease_until=null, updated_at=now(),
      error=case when attempts >= 2 then 'Worker unavailable after retry' else null end
      where status='running' and lease_until < now();
    update public.media_jobs set status='failed',stage='expired',error='Upload expired',updated_at=now()
      where status='uploading' and created_at < now()-interval '1 day';
    if exists(select 1 from public.media_jobs where status='running') then return null; end if;
    select * into j from public.media_jobs where status='queued' order by created_at limit 1;
    if not found then return null; end if;
    update public.media_jobs set status='running',stage='loading_models',attempts=attempts+1,
      lease=gen_random_uuid(),lease_until=now()+interval '120 seconds',updated_at=now()
      where id=j.id returning * into j;
    return to_jsonb(j);
  end if;
  select * into j from public.media_jobs where id=v_id for update;
  if not found then raise exception 'Job not found'; end if;
  if p_action in ('get','finalize','cancel') and j.owner is distinct from v_owner then
    raise exception 'Job not found';
  end if;
  if p_action = 'get' then return to_jsonb(j);
  elsif p_action = 'finalize' then
    if j.status='uploading' then
      update public.media_jobs set status='queued',stage='queued',updated_at=now()
        where id=j.id returning * into j;
    end if;
  elsif p_action = 'cancel' then
    update public.media_jobs set cancel_requested=true,
      status=case when status in ('uploading','queued') then 'cancelled' else status end,
      stage=case when status in ('uploading','queued') then 'cancelled' else stage end,
      updated_at=now() where id=j.id returning * into j;
  elsif p_action in ('inspect','heartbeat','complete','fail') then
    if j.status='completed' and p_action in ('inspect','complete') and j.lease=v_lease then return to_jsonb(j); end if;
    if j.status <> 'running' or j.lease is distinct from v_lease or j.lease_until < now() then
      raise exception 'Expired worker lease';
    end if;
    if p_action='inspect' then return to_jsonb(j); end if;
    if j.cancel_requested then
      update public.media_jobs set status='cancelled',stage='cancelled',updated_at=now()
        where id=j.id returning * into j;
    elsif p_action='heartbeat' then
      update public.media_jobs set lease_until=now()+interval '120 seconds',updated_at=now(),
        stage=case when p_args->>'stage' in ('loading_models','analyzing','saving')
          then p_args->>'stage' else stage end where id=j.id returning * into j;
    elsif p_action='fail' then
      update public.media_jobs set status='failed',stage='failed',error='Media processing failed',
        updated_at=now() where id=j.id returning * into j;
    else
      if p_args->'result' is null or octet_length((p_args->'result')::text)>524288 then
        raise exception 'Invalid report';
      end if;
      if j.kind <> 'clean' then
        perform public.save_scan_atomic(j.id,j.owner,j.kind,j.filename,p_args->'result',j.input_sha256);
      end if;
      update public.media_jobs set status='completed',stage='completed',result=p_args->'result',
        updated_at=now() where id=j.id returning * into j;
    end if;
  else raise exception 'Unknown action';
  end if;
  return to_jsonb(j);
end;
$$;
revoke all on function public.media_job_action(text,jsonb) from public, anon, authenticated;
grant execute on function public.media_job_action(text,jsonb) to service_role;
commit;
