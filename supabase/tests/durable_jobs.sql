-- Run inside a transaction; fixtures MUST be rolled back.
do $$
declare a uuid:=gen_random_uuid(); b uuid:=gen_random_uuid(); k uuid:=gen_random_uuid();
  j jsonb; again jsonb; claimed jsonb; old_lease text;
begin
  insert into auth.users(id,email) values(a,a::text||'@example.invalid'),(b,b::text||'@example.invalid');
  j:=public.media_job_action('reserve',jsonb_build_object('owner',a,'kind','image',
    'filename','fixture.png','input_sha256',repeat('a',64),'byte_size',100,'idempotency_key',k));
  again:=public.media_job_action('reserve',jsonb_build_object('owner',a,'kind','image',
    'filename','fixture.png','input_sha256',repeat('a',64),'byte_size',100,'idempotency_key',k));
  assert j->>'id'=again->>'id', 'duplicate reservation';
  begin
    perform public.media_job_action('get',jsonb_build_object('id',j->>'id','owner',b));
    raise exception 'Cross-owner access allowed';
  exception when others then
    if sqlerrm <> 'Job not found' then raise; end if;
  end;
  perform public.media_job_action('finalize',jsonb_build_object('id',j->>'id','owner',a));
  claimed:=public.media_job_action('claim');
  assert claimed->>'id'=j->>'id', 'wrong claim';
  assert public.media_job_action('claim') is null, 'concurrent claim';
  old_lease:=claimed->>'lease';
  update public.media_jobs set lease_until=now()-interval '1 second' where id=(j->>'id')::uuid;
  claimed:=public.media_job_action('claim');
  assert claimed->>'lease' <> old_lease, 'lease not fenced';
  begin
    perform public.media_job_action('heartbeat',jsonb_build_object('id',j->>'id','lease',old_lease));
    raise exception 'Stale heartbeat allowed';
  exception when others then
    if sqlerrm <> 'Expired worker lease' then raise; end if;
  end;
  again:=public.media_job_action('complete',jsonb_build_object('id',j->>'id','lease',claimed->>'lease',
    'result',jsonb_build_object('final_verdict','Inconclusive','confidence',0,
      'ai_generated_probability',0,'ai_edited_probability',0,'traditional_edit_probability',0,
      'authentic_probability',0)));
  assert again->>'status'='completed', 'completion failed';
  perform public.media_job_action('complete',jsonb_build_object('id',j->>'id','lease',claimed->>'lease',
    'result','{}'::jsonb));
  assert (select count(*) from public.scans where id=(j->>'id')::uuid)=1, 'duplicate scan';
  assert not has_function_privilege('anon','public.media_job_action(text,jsonb)','EXECUTE');
  assert not has_function_privilege('authenticated','public.media_job_action(text,jsonb)','EXECUTE');
  assert not has_table_privilege('authenticated','public.media_jobs','SELECT');
end;
$$;
