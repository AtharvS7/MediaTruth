"""Pinned, offline research candidates. Loading never enables a production verdict."""
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    repository: str
    revision: str
    sha256: str
    architecture: str
    input_size: int
    temperature: float = 1.0
    positive_is_real: bool = False


CANDIDATES = {
    'bfree': Candidate('grip-unina/B-Free',
        'c6a9f898782fb466b29af01f21960b67415afb0e',
        '5948ca78f4d94e820c250d24cdf155035b4a85960443800bfe6bb7f06bffe947',
        'vit_base_patch14_reg4_dinov2.lvd142m', 504),
    'community_384': Candidate('OwensLab/commfor-model-384',
        '6076002bf0d9dd37537f965ee2f06f826c333b61',
        'b89f36275f3bf5e2b040eee36597a8f19db051bff9a473a9cf7b2466284fb387',
        'vit_small_patch16_384.augreg_in21k_ft_in1k', 384),
    'community': Candidate('OwensLab/commfor-model-224',
        '26afc31e6b40c312c3fd42c05a758be62446215b',
        'a6cc439d5a6d2dfadd60c77d27a2838ad55b34e601ecd30f46ad97266d6ac4e0',
        'vit_small_patch16_224.augreg_in21k_ft_in1k', 224),
    'modern_clip': Candidate('wkaandemir/ai-image-detector',
        'fefa013737a0c3477961d36ee8dbbdc751352366',
        '41ce93c6c206a4f3929e19cf9b43b663c63a47422ab27a9bbb67757db5f42339',
        'vit_base_patch16_clip_224.openai', 256, 0.594889223575592, True),
}


def interpret_logit(logit: float, candidate: Candidate) -> dict:
    if not math.isfinite(logit):
        raise ValueError('Non-finite model output')
    scaled = logit / candidate.temperature
    positive = 1 / (1 + math.exp(-scaled)) if scaled >= 0 else math.exp(scaled) / (1 + math.exp(scaled))
    if candidate.positive_is_real:
        label = 'ai_generated' if positive < .91 else 'original' if positive >= .93 else 'inconclusive'
        score = 1 - positive
    else:
        score = positive
        label = 'ai_generated' if score > .5 else 'original'
    return {'score': score, 'label': label, 'score_semantics': 'experimental_not_calibrated_for_mediatruth'}


def build_transform(name: str):
    from torchvision import transforms as T
    if name == 'bfree':
        return T.Compose([T.ToTensor(),T.Normalize([.485,.456,.406],[.229,.224,.225])])
    if name in ('community','community_384'):
        size = CANDIDATES[name].input_size
        return T.Compose([T.Resize(256 if size==224 else 440), T.CenterCrop(size), T.ToTensor(),
                          T.Normalize([.485,.456,.406], [.229,.224,.225])])
    if name == 'modern_clip':
        return T.Compose([T.Resize((256,256)), T.ToTensor(),
                          T.Normalize([.481,.458,.408], [.269,.261,.276])])
    raise ValueError('Unknown candidate')


class GenerationCandidate:
    def __init__(self, name: str, weights: Path):
        self.name = name
        self.spec = CANDIDATES[name]
        with weights.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != self.spec.sha256:
                raise ValueError('Candidate weight hash mismatch')
        import timm
        from safetensors.torch import load_file
        if name == 'bfree':
            import torch
            from inference_pipeline.bfree_research import BFreeResearch
            checkpoint=torch.load(weights,map_location='cpu',weights_only=True)
            self.model=BFreeResearch(checkpoint['model'])
            self.model.eval()
            self.transform=build_transform(name)
            return
        state = load_file(str(weights), device='cpu')
        if name in ('community','community_384'):
            if not all(key.startswith('vit.') for key in state):
                raise ValueError('Unexpected Community Forensics weight namespace')
            state = {key.removeprefix('vit.'): value for key, value in state.items()}
        self.model = timm.create_model(self.spec.architecture, pretrained=False,
                                      num_classes=1, img_size=self.spec.input_size)
        self.model.load_state_dict(state, strict=True)
        self.model.eval()
        self.transform = build_transform(name)

    def predict(self, image):
        import torch
        with torch.inference_mode():
            tensor = self.transform(image.convert('RGB')).unsqueeze(0)
            logit = self.model(tensor).item()
        return interpret_logit(logit, self.spec)
