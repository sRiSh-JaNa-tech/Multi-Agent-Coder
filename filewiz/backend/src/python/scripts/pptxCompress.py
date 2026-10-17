import zipfile
import os
import io
import sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

IMAGE_EXTS = (".jpg", ".jpeg", ".png")
MEDIA_EXTS = (".mp4", ".mov", ".avi", ".mp3", ".wav")

QUALITY_MAP = {
    "low": 85,
    "normal": 70,
    "extreme": 45
}

MAX_WIDTH_MAP = {
    "low": None,
    "normal": 1600,
    "extreme": 1000
}

# Resampling filter: BICUBIC is ~3x-5x faster than LANCZOS with virtually zero visual loss in slides
RESAMPLE_FILTER = getattr(Image, "Resampling", Image).BICUBIC

def compress_image_bytes(raw_bytes: bytes, filename: str, level: str) -> bytes:
    """
    Compresses image bytes in memory using fast bicubic downsampling and quality reduction.
    Preserves alpha channels on PNGs to prevent black background artifacts.
    """
    try:
        # Skip small assets (icons, bullets) under 25KB to save CPU time and prevent bloating
        if len(raw_bytes) < 25 * 1024:
            return raw_bytes

        with Image.open(io.BytesIO(raw_bytes)) as img:
            orig_format = img.format or ("PNG" if filename.lower().endswith(".png") else "JPEG")
            has_alpha = img.mode in ("RGBA", "LA", "PA") or (
                "transparency" in img.info
            )

            max_width = MAX_WIDTH_MAP.get(level)
            if max_width and img.width > max_width:
                ratio = max_width / float(img.width)
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), RESAMPLE_FILTER)

            out_io = io.BytesIO()

            if has_alpha and orig_format.upper() == "PNG":
                # Preserve PNG transparency with fast compression
                img.save(out_io, "PNG", optimize=False, compress_level=6)
            else:
                # Fast JPEG compression
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(
                    out_io,
                    "JPEG",
                    quality=QUALITY_MAP.get(level, 70),
                    optimize=False
                )

            compressed_bytes = out_io.getvalue()
            # Only use compressed version if it is actually smaller
            return compressed_bytes if len(compressed_bytes) < len(raw_bytes) else raw_bytes

    except Exception:
        # If Pillow fails on any unusual format, safely retain original bytes
        return raw_bytes


def compress_pptx(input_pptx: str, output_pptx: str, level: str, remove_media: bool):
    """
    High-performance PPTX compressor:
    - Direct Zip-to-Zip stream copy for non-media files (zero disk unpacking of hundreds of XMLs)
    - Multi-core parallel image processing using ThreadPoolExecutor
    - Zero disk race conditions
    """
    if not os.path.exists(input_pptx):
        raise FileNotFoundError(f"Input file not found: {input_pptx}")

    level = level.lower() if level in QUALITY_MAP else "normal"

    with zipfile.ZipFile(input_pptx, "r") as zip_in:
        in_names = zip_in.namelist()

        # Identify image media files that require compression
        media_tasks = []
        for name in in_names:
            lower = name.lower()
            if lower.startswith("ppt/media/"):
                if remove_media and lower.endswith(MEDIA_EXTS):
                    continue  # Omit removed media
                if lower.endswith(IMAGE_EXTS):
                    media_tasks.append(name)

        # Process all media images in parallel across available CPU cores
        processed_images = {}
        if media_tasks:
            def process_entry(name):
                raw = zip_in.read(name)
                return name, compress_image_bytes(raw, name, level)

            max_workers = min(8, len(media_tasks), os.cpu_count() or 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for name, compressed_bytes in executor.map(process_entry, media_tasks):
                    processed_images[name] = compressed_bytes

        # Stream-copy all files directly into the output PPTX archive
        with zipfile.ZipFile(output_pptx, "w", compression=zipfile.ZIP_DEFLATED) as zip_out:
            for item in zip_in.infolist():
                name = item.filename
                lower = name.lower()

                # Remove video/audio if selected
                if remove_media and lower.startswith("ppt/media/") and lower.endswith(MEDIA_EXTS):
                    continue

                if name in processed_images:
                    # Write compressed image bytes
                    zip_out.writestr(name, processed_images[name])
                else:
                    # Stream copy non-media items (slides, XMLs, rels, themes) directly
                    zip_out.writestr(item, zip_in.read(name))


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python pptxCompress.py input.pptx output.pptx level removeMedia")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    compress_level = sys.argv[3]
    strip_media = sys.argv[4].lower() == "true"

    try:
        compress_pptx(input_path, output_path, compress_level, strip_media)
        print("PPTX compression completed successfully")
    except Exception as err:
        print(f"Error during PPTX compression: {err}", file=sys.stderr)
        sys.exit(1)
