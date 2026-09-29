"""Validate configuration without reflecting credentials in error messages."""
import os


def validate_configuration(env=None):
    env = os.environ if env is None else env
    for name in ('SUPABASE_URL', 'SUPABASE_SERVICE_KEY'):
        if not env.get(name):
            raise RuntimeError(f'Missing required environment variable: {name}')
    for name in ('USE_HF_API', 'ALLOW_MODEL_DOWNLOADS', 'ENABLE_LEGACY_ANALYSIS'):
        if env.get(name, 'false').lower() not in {'true', 'false', '1', '0', 'yes', 'no'}:
            raise RuntimeError(f'{name} must be a boolean; put Hugging Face credentials in HF_TOKEN')
    if env.get('JOB_BACKEND', 'local') not in {'local', 'supabase'}:
        raise RuntimeError('JOB_BACKEND must be local or supabase')
    if env.get('JOB_BACKEND') == 'supabase' and len(env.get('WORKER_SECRET', '')) < 32:
        raise RuntimeError('Durable jobs require WORKER_SECRET with at least 32 characters')
