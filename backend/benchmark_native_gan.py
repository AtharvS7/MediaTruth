"""Experimental native GAN scores. Does not enable or tune production verdicts."""
import argparse
import json
import os
from pathlib import Path

from evaluation import read_manifest, wilson


def run(manifest: Path, output: Path):
    if output.exists():
        raise ValueError('Choose a new output path; preserve previous benchmark evidence')
    rows = [r for r in read_manifest(manifest) if r['split'] == 'test']
    if not rows or any(r['label'] not in {'original', 'ai_generated'} for r in rows):
        raise ValueError('This binary probe supports only original and AI-generated samples')
    os.environ['USE_HF_API'] = 'false'
    os.environ['ALLOW_MODEL_DOWNLOADS'] = 'false'
    import torch
    from services.model_loader import ModelLoader
    from inference_pipeline.gan_detector import GANDetector
    torch.set_num_threads(2)
    loader = ModelLoader()
    loader._load_cnn_detect()
    detector = GANDetector(loader)
    predictions = []
    for row in rows:
        result = detector.predict(str((manifest.parent/row['path']).resolve()))
        available = result['api_success']
        predictions.append({'id': row['id'], 'sha256': row['sha256'], 'truth': row['label'],
            'available': available, 'score': result['score'] if available else None,
            'detector_positive': result['score'] > .5 if available else None})
    positives = [r for r in predictions if r['truth'] == 'ai_generated']
    negatives = [r for r in predictions if r['truth'] == 'original']
    detected = sum(r['detector_positive'] is True for r in positives)
    false_flags = sum(r['detector_positive'] is True for r in negatives)
    report = {'scope': 'Exploratory binary probe; no release approval, calibration or deployment change',
        'transform': 'RGB; center crop 224 without resize; ImageNet normalization',
        'threshold': .5, 'threshold_selection': 'existing fixed threshold; not tuned on pilot',
        'model_weights_sha256': loader.weight_fingerprints,
        'samples': len(predictions), 'failures': sum(not r['available'] for r in predictions),
        'synthetic_count': len(positives), 'synthetic_flagged': detected,
        'synthetic_detection_rate': detected/len(positives) if positives else None,
        'synthetic_detection_rate_95': wilson(detected, len(positives)),
        'original_count': len(negatives),
        'original_false_positive_rate': false_flags/len(negatives) if negatives else None,
        'parent_independence_verified': False, 'predictions': predictions}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('samples', 'failures', 'synthetic_flagged', 'original_count')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    run(args.manifest, args.output)
