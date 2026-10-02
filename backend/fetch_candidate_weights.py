"""Explicit operator download of pinned research weights; no automatic deployment."""
import argparse
import hashlib
from pathlib import Path
import tempfile

import requests
from inference_pipeline.generation_candidates import CANDIDATES

SIZES = {'community': 86678644, 'community_384': 87262324, 'modern_clip': 343399284}


def fetch(name, directory):
    spec = CANDIDATES[name]
    directory.mkdir(parents=True, exist_ok=True)
    target = directory/f'{name}.safetensors'
    if target.exists():
        with target.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest() != spec.sha256:
                raise ValueError('Existing artifact hash mismatch; preserved for inspection')
        return target
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory,suffix='.partial',delete=False) as stream:
            temporary = Path(stream.name)
            digest, total = hashlib.sha256(), 0
            url=f'https://huggingface.co/{spec.repository}/resolve/{spec.revision}/model.safetensors'
            with requests.get(url,stream=True,timeout=(30,120)) as response:
                response.raise_for_status()
                for chunk in response.iter_content(1024*1024):
                    total += len(chunk)
                    if total > SIZES[name]:
                        raise ValueError('Artifact exceeds expected size')
                    stream.write(chunk)
                    digest.update(chunk)
        if total != SIZES[name] or digest.hexdigest() != spec.sha256:
            raise ValueError('Artifact size or hash mismatch')
        # Windows rename refuses to replace a concurrently installed artifact.
        temporary.rename(target)
        return target
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate',choices=SIZES)
    p.add_argument('--directory',type=Path,default=Path(__file__).parent/'models'/'weights')
    a=p.parse_args()
    print('Verified research artifact:',fetch(a.candidate,a.directory).name)
