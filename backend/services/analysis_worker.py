"""Isolated, disposable inference process. No database credentials are needed."""
import argparse
import asyncio
import json
from pathlib import Path


async def run(args):
    if args.kind == "clean":
        from services.metadata_cleaner import clean_image_metadata
        Path(args.output).write_bytes(clean_image_metadata(args.input))
        return
    from services.model_loader import ModelLoader
    from services.image_analyzer import ImageAnalyzer
    from services.video_analyzer import VideoAnalyzer
    def stage(value):
        Path(args.progress).write_text(value, encoding="utf-8")
    stage("loading_models")
    loader = ModelLoader()
    await loader.load_all_models()
    stage("analyzing")
    analyzer = ImageAnalyzer(loader) if args.kind == "image" else VideoAnalyzer(loader)
    result = await analyzer.analyze(args.input, args.id)
    Path(args.output).write_text(json.dumps(result, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("kind", "input", "output", "progress", "id"):
        parser.add_argument("--" + name, required=True)
    asyncio.run(run(parser.parse_args()))
