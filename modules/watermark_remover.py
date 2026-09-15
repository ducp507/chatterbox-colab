"""
Batch-remove Google Flow's watermark (the small sparkle icon Flow always
burns into the bottom-right corner of exported frames) from a folder of
images.

Flow's icon sits at a fixed position/size on every export at its standard
1376x768 resolution, so this skips watermark *detection* entirely (no YOLO,
no AI locating step) and just always inpaints the same corner box, scaled
to whatever resolution the uploaded images actually are. That's simpler and
more reliable here than a general-purpose watermark remover (e.g. YOLO+LAMA
tools like SoraWatermarkCleaner) would be, since those are trained to find
a *different* watermark shape (Sora's) and would need retraining to detect
Flow's icon.

The actual inpainting is LaMa (Advimman) via its public torchscript export,
the same model SoraWatermarkCleaner and most watermark/object removers use
under the hood. Model-loading code below is trimmed from
github.com/enesmsahin/simple-lama-inpainting (Apache 2.0) -- vendored
in directly (rather than pip-installed) because that package pins
numpy<2.0, which would fight Colab's base image numpy (see the warning in
requirements-colab.txt). We drop its unused image-downscaling path, whose
only reason for existing was to lean on cv2 -- so no new dependency here at
all: everything below runs on torch/numpy/Pillow, already in requirements.
"""
import os
import zipfile
import tempfile

import numpy as np
import torch
from PIL import Image, ImageDraw
from torch.hub import download_url_to_file, get_dir

from .config import DEVICE

LAMA_MODEL_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"

# Measured directly on Google Flow's fixed 1376x768 export (bottom-right
# sparkle icon), with a little padding around the glyph's antialiased edges.
# Expressed as offsets from the image edges so they scale to any resolution.
REF_W, REF_H = 1376, 768
REF_RIGHT_MARGIN = 65
REF_BOTTOM_MARGIN = 60
REF_BOX_W = 70
REF_BOX_H = 75

_model = None  # lazy singleton, loaded once per process


def _cache_path():
    model_dir = os.path.join(get_dir(), "checkpoints")
    os.makedirs(model_dir, exist_ok=True)
    return os.path.join(model_dir, "big-lama.pt")


def _load_model():
    global _model
    if _model is None:
        path = _cache_path()
        if not os.path.exists(path):
            download_url_to_file(LAMA_MODEL_URL, path, None, progress=True)
        _model = torch.jit.load(path, map_location=DEVICE)
        _model.eval()
        _model.to(DEVICE)
    return _model


def _ceil_modulo(x, mod):
    return x if x % mod == 0 else (x // mod + 1) * mod


def _inpaint(image: Image.Image, mask: Image.Image) -> Image.Image:
    """image: RGB PIL Image. mask: 'L' PIL Image, 255 = area to remove."""
    model = _load_model()

    img = np.array(image).astype(np.float32).transpose(2, 0, 1) / 255.0
    msk = np.array(mask).astype(np.float32)[np.newaxis, ...] / 255.0
    c, h, w = img.shape
    out_h, out_w = _ceil_modulo(h, 8), _ceil_modulo(w, 8)
    img = np.pad(img, ((0, 0), (0, out_h - h), (0, out_w - w)), mode="symmetric")
    msk = np.pad(msk, ((0, 0), (0, out_h - h), (0, out_w - w)), mode="symmetric")

    img_t = torch.from_numpy(img).unsqueeze(0).to(DEVICE)
    msk_t = (torch.from_numpy(msk).unsqueeze(0).to(DEVICE) > 0) * 1

    with torch.inference_mode():
        result = model(img_t, msk_t)

    result = result[0].permute(1, 2, 0).detach().cpu().numpy()
    result = np.clip(result * 255, 0, 255).astype(np.uint8)[:h, :w]
    return Image.fromarray(result)


def build_mask(width, height, right_margin=None, bottom_margin=None, box_w=None, box_h=None):
    """White (255) box in the bottom-right corner, scaled from the reference
    1376x768 measurement to whatever resolution the actual image is."""
    sx, sy = width / REF_W, height / REF_H
    right_margin = REF_RIGHT_MARGIN * sx if right_margin is None else right_margin
    bottom_margin = REF_BOTTOM_MARGIN * sy if bottom_margin is None else bottom_margin
    box_w = REF_BOX_W * sx if box_w is None else box_w
    box_h = REF_BOX_H * sy if box_h is None else box_h

    x1 = width - right_margin
    x0 = x1 - box_w
    y1 = height - bottom_margin
    y0 = y1 - box_h

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rectangle([x0, y0, x1, y1], fill=255)
    return mask


def _file_path(f):
    return f.name if hasattr(f, "name") else f


def preview_watermark_mask(files, right_margin, bottom_margin, box_w, box_h):
    """Draw the mask box (no inpainting) on the first uploaded image, so the
    fixed-position box can be sanity-checked before running a whole batch."""
    if not files:
        return None
    img = Image.open(_file_path(files[0])).convert("RGB")
    mask = build_mask(img.width, img.height, right_margin, bottom_margin, box_w, box_h)
    overlay = img.copy()
    bbox = mask.getbbox()
    if bbox:
        ImageDraw.Draw(overlay).rectangle(bbox, outline=(255, 0, 0), width=3)
    return overlay


def remove_watermark_batch(files, right_margin, bottom_margin, box_w, box_h):
    """Generator: yields (progress_0_100, status_text, preview_gallery, zip_path).
    zip_path is only set on the final yield."""
    try:
        if not files:
            yield 0, "❌ Error: Chưa chọn ảnh nào.", None, None
            return

        out_dir = tempfile.mkdtemp(prefix="watermark_removed_")
        preview = []
        n = len(files)
        for i, f in enumerate(files):
            src_path = _file_path(f)
            img = Image.open(src_path).convert("RGB")
            mask = build_mask(img.width, img.height, right_margin, bottom_margin, box_w, box_h)
            cleaned = _inpaint(img, mask)

            out_name = os.path.basename(src_path)
            cleaned.save(os.path.join(out_dir, out_name), quality=95)
            if len(preview) < 6:
                preview.append((cleaned, out_name))

            yield int(((i + 1) / n) * 95), f"Đang xử lý {i + 1}/{n}: {out_name}...", preview, None

        zip_path = os.path.join(tempfile.mkdtemp(prefix="watermark_zip_"), "cleaned_images.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for fn in os.listdir(out_dir):
                zf.write(os.path.join(out_dir, fn), arcname=fn)

        yield 100, f"✅ Xong! Đã xoá watermark {n} ảnh.", preview, zip_path

    except Exception as e:
        yield 0, f"❌ Error: {str(e)}", None, None
