-- Trigger execution does not require browser RPC access.
revoke execute on function public.handle_new_user() from public, anon, authenticated;
