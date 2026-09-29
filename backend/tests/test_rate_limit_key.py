from types import SimpleNamespace
from utils.auth import rate_limit_key


def request(token, owner=None):
    return SimpleNamespace(headers={'Authorization': 'Bearer ' + token},
                           state=SimpleNamespace(user_id=owner), client=SimpleNamespace(host='1.2.3.4'))


def test_forged_tokens_share_ip_bucket():
    assert rate_limit_key(request('forged-a')) == rate_limit_key(request('forged-b')) == 'ip:1.2.3.4'


def test_rotated_tokens_share_verified_owner_bucket():
    assert rate_limit_key(request('old', 'owner')) == rate_limit_key(request('new', 'owner')) == 'user:owner'


def test_different_owners_have_separate_buckets():
    assert rate_limit_key(request('a', 'one')) != rate_limit_key(request('b', 'two'))
