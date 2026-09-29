"""Create/delete an isolated browser-test account; never sends mail."""
import io
import json
import base64
from pathlib import Path
import secrets
import sys
import uuid
from dotenv import dotenv_values
from PIL import Image
from supabase import create_client

v = dotenv_values(Path(__file__).resolve().parents[1] / '.env')
c = create_client(v['SUPABASE_URL'], v['SUPABASE_SERVICE_KEY'])
if sys.argv[1] == 'create':
    email = f'mediatruth-browser-{uuid.uuid4()}@example.invalid'
    password = secrets.token_urlsafe(32)
    user = c.auth.admin.create_user({'email': email, 'password': password, 'email_confirm': True}).user
    media = io.BytesIO()
    Image.new('RGBA', (16,16), (20,50,80,128)).save(media, format='PNG')
    print(json.dumps({'email': email, 'password': password, 'id': user.id,
                      'png': base64.b64encode(media.getvalue()).decode()}))
elif sys.argv[1] == 'delete':
    owner = str(uuid.UUID(sys.argv[2]))
    user = c.auth.admin.get_user_by_id(owner).user
    if not user.email.startswith('mediatruth-browser-') or not user.email.endswith('@example.invalid'):
        raise SystemExit('Refusing to delete a non-fixture account')
    rows = c.table('media_jobs').select('id').eq('owner', owner).execute().data
    for row in rows:
        prefix = f"{owner}/{row['id']}"
        c.storage.from_('mediatruth-jobs').remove([prefix+'/input',prefix+'/output.png'])
    c.table('media_jobs').delete().eq('owner',owner).execute()
    c.table('scans').delete().eq('user_id',owner).execute()
    c.auth.admin.delete_user(owner)
    print('Browser fixture removed')
