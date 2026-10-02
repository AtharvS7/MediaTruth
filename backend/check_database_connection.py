"""Read-only PostgreSQL connection check. Never prints the DSN or credentials."""
import os
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlsplit

from dotenv import dotenv_values


def main():
    values = dotenv_values(Path(__file__).with_name('.env'))
    parsed = urlsplit(values.get('SUPABASE_DB_URL') or '')
    if parsed.scheme not in {'postgres', 'postgresql'} or not parsed.hostname or not parsed.password:
        raise SystemExit('Set a complete SUPABASE_DB_URL in backend/.env')
    env = dict(os.environ)
    env.update(PGHOST=parsed.hostname, PGPORT=str(parsed.port or 5432),
               PGUSER=unquote(parsed.username or 'postgres'),
               PGPASSWORD=unquote(parsed.password), PGDATABASE=parsed.path.lstrip('/') or 'postgres',
               PGSSLMODE='require', PGCONNECT_TIMEOUT='10')
    command = ['docker', 'run', '--rm']
    for name in ('PGHOST', 'PGPORT', 'PGUSER', 'PGPASSWORD', 'PGDATABASE', 'PGSSLMODE', 'PGCONNECT_TIMEOUT'):
        command += ['--env', name]
    command += ['public.ecr.aws/supabase/postgres:17.6.1.155', 'psql', '-X', '-v', 'ON_ERROR_STOP=1',
                '-Atc', "SELECT current_setting('server_version_num'), EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='scans');"]
    try:
        result = subprocess.run(command, env=env, capture_output=True, timeout=40)
    except subprocess.TimeoutExpired:
        raise SystemExit('Database check timed out; no credentials were printed') from None
    if result.returncode:
        error = result.stderr.decode(errors='replace').lower()
        reason = ('authentication failed' if 'password authentication failed' in error else
                  'host name could not be resolved' if 'could not translate host' in error else
                  'network connection unavailable' if any(x in error for x in ('network is unreachable', 'timeout', 'timed out')) else
                  'connection failed; credentials and provider details suppressed')
        raise SystemExit(reason)
    print('PostgreSQL connection succeeded; schema check:', result.stdout.decode().strip())


if __name__ == '__main__':
    main()
