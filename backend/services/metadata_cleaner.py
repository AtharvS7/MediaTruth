"""Export decoded pixels without source metadata; pixel watermarks may remain."""
import io
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_EXPORT_PIXELS = 16_000_000


def clean_image_metadata(image_path: str) -> bytes:
    try:
        with Image.open(image_path) as source:
            if source.format not in {"JPEG", "PNG", "WEBP", "BMP"}:
                raise ValueError("Supported formats: JPEG, PNG, WebP, BMP.")
            if source.width * source.height > MAX_EXPORT_PIXELS:
                raise ValueError("Metadata export supports images up to 16 megapixels.")
            if getattr(source, "n_frames", 1) != 1:
                raise ValueError("Animated images are not supported for metadata export.")
            oriented = ImageOps.exif_transpose(source)
            mode = "RGBA" if "A" in oriented.getbands() or "transparency" in source.info else "RGB"
            converted = oriented.convert(mode)
            # A fresh image prevents implicit EXIF, XMP, ICC, PNG text or comments
            # from being copied by Pillow's encoder.
            clean = Image.new(mode, converted.size)
            clean.paste(converted)
            output = io.BytesIO()
            clean.save(output, format="PNG")
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("The image could not be safely decoded.") from exc
