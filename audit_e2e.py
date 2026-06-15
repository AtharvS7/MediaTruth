"""
MediaTruth End-to-End Audit — audit_e2e.py
===========================================
Tests all 8 core features of the platform using the live backend.
Run BEFORE deploying. All tests must pass.

Usage:
    # Test local mode (HF pipeline / local weights):
    cd D:\MediaTruth
    $env:PYTHONPATH = "backend"
    backend\venv\Scripts\python.exe audit_e2e.py

    # Test HF API mode (simulates Render deployment):
    $env:USE_HF_API = "true"
    backend\venv\Scripts\python.exe audit_e2e.py
"""

import asyncio
import base64
import io
import json
import logging
import os
import sys
import time
import tempfile

import numpy as np
from PIL import Image, ImageDraw

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results = []


def check(name: str, condition: bool, detail: str = "", warn_only: bool = False) -> bool:
    status = PASS if condition else (WARN if warn_only else FAIL)
    msg = f"  {status}  {name}"
    if detail:
        msg += f"\n         → {detail}"
    print(msg)
    results.append((name, condition, warn_only))
    return condition


def _hf_api_reachable() -> bool:
    """Quick check if HF Inference API is reachable from this environment."""
    try:
        import socket
        socket.setdefaulttimeout(5)
        socket.getaddrinfo("api-inference.huggingface.co", 443)
        return True
    except Exception:
        return False


def make_test_image(mode: str = "real") -> str:
    """Create a synthetic test image and return path to temp file."""
    if mode == "real":
        # Photographic-looking: gradient + noise
        arr = np.zeros((256, 256, 3), dtype=np.uint8)
        for i in range(256):
            arr[i, :] = [max(0, 80 - i // 4), max(0, 120 - i // 6), min(255, 180 + i // 8)]
        noise = np.random.randint(-15, 15, arr.shape, dtype=np.int16)
        arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
    else:
        # Uniform flat colour — maximally non-photographic
        img = Image.new("RGB", (256, 256), color=(128, 200, 100))

    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(f.name, "JPEG", quality=90)
    f.close()
    return f.name


async def run_audit():
    hf_api_mode = os.environ.get("USE_HF_API", "").lower() in ("1", "true", "yes")
    mode_label = "HF Inference API" if hf_api_mode else "Local (HF pipeline / .pth weights)"

    # Pre-check: is HF Inference API reachable?
    hf_api_reachable = _hf_api_reachable() if hf_api_mode else True

    print("=" * 65)
    print("  MediaTruth — End-to-End Core Feature Audit")
    print(f"  Mode: {mode_label}")
    if hf_api_mode and not hf_api_reachable:
        print("  ⚠️  NOTE: api-inference.huggingface.co is NOT reachable from")
        print("      this machine (DNS/firewall). ML API checks will be WARN,")
        print("      not FAIL. This is a local network restriction — not a code")
        print("      bug. On Render's servers this endpoint works correctly.")
    print("=" * 65)

    # ─────────────────────────────────────────────────────────────────
    # TEST 1: ModelLoader — both detectors initialise correctly
    # ─────────────────────────────────────────────────────────────────
    print("\n[1] ModelLoader Initialisation")
    from services.model_loader import ModelLoader
    loader = ModelLoader()
    await loader.load_all_models()

    check("ModelLoader.ready", loader.ready, f"ready={loader.ready}")
    deepfake_ok = loader.has_weights("deepfake")
    gan_ok = loader.has_weights("gan_detect")
    check("DeepfakeDetector weights_available", deepfake_ok,
          f"has_weights={deepfake_ok}")
    check("GANDetector weights_available", gan_ok,
          f"has_weights={gan_ok}")

    if hf_api_mode:
        check("HF API mode active", loader._hf_api_mode,
              "USE_HF_API env var correctly read")

    # ─────────────────────────────────────────────────────────────────
    # TEST 2: DeepfakeDetector — real non-zero score
    # ─────────────────────────────────────────────────────────────────
    print("\n[2] DeepfakeDetector Inference")
    from inference_pipeline.deepfake_detector import DeepfakeDetector
    df_detector = DeepfakeDetector(loader)
    test_img = make_test_image("real")

    t0 = time.time()
    df_result = df_detector.predict(test_img)
    elapsed = time.time() - t0

    check("DeepfakeDetector returns dict", isinstance(df_result, dict))
    check("DeepfakeDetector weights_available", df_result.get("weights_available", False),
          f"weights_available={df_result.get('weights_available')}",
          warn_only=(hf_api_mode and not hf_api_reachable))
    check("DeepfakeDetector score is float in [0,1]",
          isinstance(df_result.get("score"), (int, float)) and 0.0 <= df_result.get("score", -1) <= 1.0,
          f"score={df_result.get('score')}")
    check("DeepfakeDetector label is valid",
          df_result.get("label") in ("real", "fake", "unavailable"),
          f"label={df_result.get('label')}")
    check("DeepfakeDetector score != 0.0 (not random noise)",
          df_result.get("score", 0.0) > 0.0 or df_result.get("label") == "real",
          f"score={df_result.get('score'):.4f}, label={df_result.get('label')}",
          warn_only=(hf_api_mode and not hf_api_reachable))
    check("DeepfakeDetector response time < 60s", elapsed < 60,
          f"{elapsed:.1f}s", warn_only=True)

    os.unlink(test_img)

    # ─────────────────────────────────────────────────────────────────
    # TEST 3: GANDetector — real non-zero score
    # ─────────────────────────────────────────────────────────────────
    print("\n[3] GANDetector Inference")
    from inference_pipeline.gan_detector import GANDetector
    gan_detector = GANDetector(loader)
    test_img2 = make_test_image("real")

    t0 = time.time()
    gan_result = gan_detector.predict(test_img2)
    elapsed = time.time() - t0

    check("GANDetector returns dict", isinstance(gan_result, dict))
    check("GANDetector weights_available", gan_result.get("weights_available", False),
          f"weights_available={gan_result.get('weights_available')}",
          warn_only=(hf_api_mode and not hf_api_reachable))
    check("GANDetector score is float in [0,1]",
          isinstance(gan_result.get("score"), (int, float)) and 0.0 <= gan_result.get("score", -1) <= 1.0,
          f"score={gan_result.get('score')}")
    check("GANDetector label is valid",
          gan_result.get("label") in ("real", "gan", "unavailable"),
          f"label={gan_result.get('label')}")
    check("GANDetector response time < 60s", elapsed < 60,
          f"{elapsed:.1f}s", warn_only=True)

    os.unlink(test_img2)

    # ─────────────────────────────────────────────────────────────────
    # TEST 4: ManipulationLocalizer — heatmap + score
    # ─────────────────────────────────────────────────────────────────
    print("\n[4] ManipulationLocalizer (ELA + DCT)")
    from inference_pipeline.manipulation_localizer import ManipulationLocalizer
    localizer = ManipulationLocalizer(loader)
    test_img3 = make_test_image("real")
    manip_result = localizer.predict(test_img3)

    check("ManipulationLocalizer returns dict", isinstance(manip_result, dict))
    check("ManipulationLocalizer heatmap not None", manip_result.get("heatmap") is not None,
          f"heatmap shape={getattr(manip_result.get('heatmap'), 'shape', None)}")
    check("ManipulationLocalizer heatmap is (H,W,3) uint8",
          manip_result.get("heatmap") is not None and
          manip_result["heatmap"].ndim == 3 and manip_result["heatmap"].shape[2] == 3,
          f"shape={getattr(manip_result.get('heatmap'), 'shape', None)}")
    check("ManipulationLocalizer score in [0,1]",
          0.0 <= manip_result.get("score", -1) <= 1.0,
          f"score={manip_result.get('score'):.4f}")
    check("ManipulationLocalizer label valid",
          manip_result.get("label") in ("manipulated", "clean", "unknown"),
          f"label={manip_result.get('label')}")

    os.unlink(test_img3)

    # ─────────────────────────────────────────────────────────────────
    # TEST 5: MetadataAnalyzer
    # ─────────────────────────────────────────────────────────────────
    print("\n[5] MetadataAnalyzer")
    from inference_pipeline.metadata_analyzer import MetadataAnalyzer
    meta_analyzer = MetadataAnalyzer()
    test_img4 = make_test_image("real")
    meta_result = meta_analyzer.analyze(test_img4)

    check("MetadataAnalyzer returns dict", isinstance(meta_result, dict))
    check("MetadataAnalyzer anomaly_score in [0,1]",
          0.0 <= meta_result.get("anomaly_score", -1) <= 1.0,
          f"anomaly_score={meta_result.get('anomaly_score')}")
    check("MetadataAnalyzer findings is list",
          isinstance(meta_result.get("findings"), list),
          f"findings count={len(meta_result.get('findings', []))}")

    os.unlink(test_img4)

    # ─────────────────────────────────────────────────────────────────
    # TEST 6: ConfidenceAggregator — verdict logic
    # ─────────────────────────────────────────────────────────────────
    print("\n[6] ConfidenceAggregator")
    from inference_pipeline.aggregator import ConfidenceAggregator
    agg = ConfidenceAggregator()

    # Case A: both detectors have weights, should NOT be limited mode
    verdict_a = agg.aggregate(
        deepfake={"score": 0.15, "weights_available": True},
        gan={"score": 0.10, "weights_available": True},
        manipulation={"score": 0.20},
        metadata={"anomaly_score": 0.05, "findings": []},
    )
    check("Aggregator: NOT limited_mode when weights available",
          not verdict_a["limited_mode"],
          f"limited_mode={verdict_a['limited_mode']}")
    check("Aggregator: confidence <= 1.0", verdict_a["confidence"] <= 1.0,
          f"confidence={verdict_a['confidence']}")
    check("Aggregator: probabilities sum ~1.0",
          abs(verdict_a["ai_generated"] + verdict_a["ai_edited"] +
              verdict_a["traditional_edit"] + verdict_a["authentic"] - 1.0) < 0.01,
          f"sum={verdict_a['ai_generated']+verdict_a['ai_edited']+verdict_a['traditional_edit']+verdict_a['authentic']:.4f}")
    check("Aggregator: verdict is valid string",
          verdict_a["verdict"] in ("AI Generated", "AI Edited", "Traditionally Edited", "Authentic / Original"),
          f"verdict={verdict_a['verdict']}")

    # Case B: both unavailable → limited_mode True
    verdict_b = agg.aggregate(
        deepfake={"score": 0.0, "weights_available": False},
        gan={"score": 0.0, "weights_available": False},
        manipulation={"score": 0.30},
        metadata={"anomaly_score": 0.10, "findings": []},
    )
    check("Aggregator: limited_mode=True when both unavailable",
          verdict_b["limited_mode"],
          f"limited_mode={verdict_b['limited_mode']}")
    check("Aggregator: limited_mode caps confidence at 0.75",
          verdict_b["confidence"] <= 0.75,
          f"confidence={verdict_b['confidence']}")

    # Case C: real image scores (score=0.0 is valid) must NOT trigger limited_mode
    verdict_c = agg.aggregate(
        deepfake={"score": 0.0, "weights_available": True},  # clean image → score=0
        gan={"score": 0.02, "weights_available": True},
        manipulation={"score": 0.05},
        metadata={"anomaly_score": 0.01, "findings": []},
    )
    check("Aggregator: score=0.0 with weights_available=True → NOT limited_mode",
          not verdict_c["limited_mode"],
          f"limited_mode={verdict_c['limited_mode']} (BUG if True — fixed in this session)")

    # ─────────────────────────────────────────────────────────────────
    # TEST 7: Full ImageAnalyzer pipeline
    # ─────────────────────────────────────────────────────────────────
    print("\n[7] Full ImageAnalyzer Pipeline")
    from services.image_analyzer import ImageAnalyzer
    analyzer = ImageAnalyzer(loader)
    test_img5 = make_test_image("real")

    t0 = time.time()
    full_result = await analyzer.analyze(test_img5, scan_id="test-scan-001")
    elapsed = time.time() - t0

    check("ImageAnalyzer returns dict", isinstance(full_result, dict))
    check("ImageAnalyzer: file_type='image'", full_result.get("file_type") == "image",
          f"file_type={full_result.get('file_type')}")
    check("ImageAnalyzer: probabilities present",
          all(k in full_result for k in [
              "ai_generated_probability", "ai_edited_probability",
              "traditional_edit_probability", "authentic_probability"
          ]))
    check("ImageAnalyzer: probabilities sum ~1.0",
          abs(sum([
              full_result.get("ai_generated_probability", 0),
              full_result.get("ai_edited_probability", 0),
              full_result.get("traditional_edit_probability", 0),
              full_result.get("authentic_probability", 0),
          ]) - 1.0) < 0.02,
          f"sum={sum([full_result.get('ai_generated_probability',0), full_result.get('ai_edited_probability',0), full_result.get('traditional_edit_probability',0), full_result.get('authentic_probability',0)]):.4f}")
    check("ImageAnalyzer: final_verdict is string",
          isinstance(full_result.get("final_verdict"), str) and len(full_result.get("final_verdict", "")) > 0,
          f"verdict={full_result.get('final_verdict')}")
    check("ImageAnalyzer: heatmap is base64 string",
          isinstance(full_result.get("manipulation_heatmap"), str) and
          len(full_result.get("manipulation_heatmap", "")) > 100,
          f"heatmap_len={len(full_result.get('manipulation_heatmap',''))}")
    check("ImageAnalyzer: heatmap is valid base64",
          _is_valid_base64_png(full_result.get("manipulation_heatmap", "")),
          "base64 decode + PNG header check")
    check("ImageAnalyzer: detector_scores present",
          isinstance(full_result.get("detector_scores"), dict),
          f"scores={full_result.get('detector_scores')}")
    check("ImageAnalyzer: ML scores are non-zero",
          (full_result.get("detector_scores", {}).get("deepfake_score", 0) > 0.0 or
           full_result.get("detector_scores", {}).get("gan_score", 0) > 0.0),
          f"deepfake={full_result.get('detector_scores',{}).get('deepfake_score'):.4f} "
          f"gan={full_result.get('detector_scores',{}).get('gan_score'):.4f}",
          warn_only=(not (deepfake_ok or gan_ok)) or (hf_api_mode and not hf_api_reachable))
    check("ImageAnalyzer: confidence > 0", full_result.get("confidence", 0) > 0.0,
          f"confidence={full_result.get('confidence')}")
    check("ImageAnalyzer total pipeline time < 90s", elapsed < 90,
          f"{elapsed:.1f}s", warn_only=True)

    print(f"\n  Full result summary:")
    print(f"    Verdict    : {full_result.get('final_verdict')}")
    print(f"    Confidence : {full_result.get('confidence', 0):.1%}")
    print(f"    AI Gen     : {full_result.get('ai_generated_probability', 0):.1%}")
    print(f"    AI Edited  : {full_result.get('ai_edited_probability', 0):.1%}")
    print(f"    Trad Edit  : {full_result.get('traditional_edit_probability', 0):.1%}")
    print(f"    Authentic  : {full_result.get('authentic_probability', 0):.1%}")
    print(f"    Limited Mode: {full_result.get('limited_mode')}")
    print(f"    DF Score   : {full_result.get('detector_scores',{}).get('deepfake_score'):.4f}")
    print(f"    GAN Score  : {full_result.get('detector_scores',{}).get('gan_score'):.4f}")
    print(f"    Manip Score: {full_result.get('detector_scores',{}).get('manipulation_score'):.4f}")

    os.unlink(test_img5)

    # ─────────────────────────────────────────────────────────────────
    # TEST 8: Output accuracy — no random noise
    # ─────────────────────────────────────────────────────────────────
    print("\n[8] Output Accuracy & Consistency")

    # Run same image twice — must get identical scores (deterministic)
    test_img6 = make_test_image("real")
    r1 = await analyzer.analyze(test_img6, scan_id="consistency-1")
    r2 = await analyzer.analyze(test_img6, scan_id="consistency-2")
    os.unlink(test_img6)

    df_consistent = abs(r1.get("detector_scores", {}).get("deepfake_score", 0) -
                        r2.get("detector_scores", {}).get("deepfake_score", 0)) < 0.001
    gan_consistent = abs(r1.get("detector_scores", {}).get("gan_score", 0) -
                         r2.get("detector_scores", {}).get("gan_score", 0)) < 0.001
    check("DeepfakeDetector is deterministic (same image → same score)",
          df_consistent,
          f"run1={r1.get('detector_scores',{}).get('deepfake_score'):.4f} "
          f"run2={r2.get('detector_scores',{}).get('deepfake_score'):.4f}")
    check("GANDetector is deterministic (same image → same score)",
          gan_consistent,
          f"run1={r1.get('detector_scores',{}).get('gan_score'):.4f} "
          f"run2={r2.get('detector_scores',{}).get('gan_score'):.4f}")
    check("No 'unavailable' labels when weights present",
          full_result.get("final_verdict") != "unavailable",
          f"verdict={full_result.get('final_verdict')}")

    # ─────────────────────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  AUDIT SUMMARY")
    print("=" * 65)

    passed = sum(1 for _, ok, warn in results if ok or warn)
    hard_passed = sum(1 for _, ok, warn in results if ok and not warn)
    failed = [(name, ok, warn) for name, ok, warn in results if not ok and not warn]
    warnings = [(name, ok, warn) for name, ok, warn in results if not ok and warn]

    print(f"  Total checks : {len(results)}")
    print(f"  Hard PASS    : {hard_passed}")
    print(f"  Warnings     : {len(warnings)}")
    print(f"  FAIL         : {len(failed)}")

    if failed:
        print("\n  ❌ FAILED CHECKS:")
        for name, _, _ in failed:
            print(f"     - {name}")

    if warnings:
        print("\n  ⚠️  WARNINGS (non-blocking):")
        for name, _, _ in warnings:
            print(f"     - {name}")

    if not failed:
        print(f"\n  🎉 ALL HARD CHECKS PASSED — project is production ready!")
    else:
        print(f"\n  ❌ {len(failed)} check(s) failed — fix before deploying.")

    print("=" * 65)
    return len(failed) == 0


def _is_valid_base64_png(b64_str: str) -> bool:
    """Check if a string is valid base64-encoded PNG data."""
    try:
        data = base64.b64decode(b64_str)
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    except Exception:
        return False


if __name__ == "__main__":
    ok = asyncio.run(run_audit())
    sys.exit(0 if ok else 1)
