#!/usr/bin/env python3
"""
square_converter — A4 → 1:1 batch image converter
Supports PNG, JPEG, PDF (single & multi-page)

Modes:
  pad    — add white borders (no content loss)
  crop   — center crop
  smart  — auto-detect content area, strip whitespace, pad to square

Barcode safety:
  - Barcodes are verified before/after conversion
  - Files with barcodes are always saved as PNG (lossless)
  - Conversion aborts if a barcode is lost

Usage:
    python convert.py <input_dir> <output_dir> [--mode smart|pad|crop] [--dpi 150]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
import fitz  # PyMuPDF

from barcode_check import verify, PYZBAR_AVAILABLE, BarcodeIntegrityError


SUPPORTED = {".png", ".jpg", ".jpeg", ".pdf"}


# ─── Core transformations ─────────────────────────────────────────────────────

def ensure_rgb(img):
    return img.convert("RGB") if img.mode in ("RGBA","LA","P") else img

def pad_to_square(img, bg=(255,255,255)):
    img = ensure_rgb(img)
    w, h = img.size
    size = max(w, h)
    out = Image.new("RGB", (size, size), bg)
    out.paste(img, ((size-w)//2, (size-h)//2))
    return out

def center_crop(img):
    img = ensure_rgb(img)
    w, h = img.size
    size = min(w, h)
    return img.crop(((w-size)//2,(h-size)//2,(w+size)//2,(h+size)//2))

def smart_crop(img, padding_pct=0.03, threshold=200):
    img = ensure_rgb(img)
    gray = np.array(img.convert("L"))
    h, w = gray.shape
    rows = np.any(gray < threshold, axis=1)
    cols = np.any(gray < threshold, axis=0)
    if not rows.any() or not cols.any():
        return pad_to_square(img)
    top    = int(np.argmax(rows))
    bottom = int(len(rows) - np.argmax(rows[::-1]))
    left   = int(np.argmax(cols))
    right  = int(len(cols) - np.argmax(cols[::-1]))
    pad = int(max(bottom-top, right-left) * padding_pct)
    cropped = img.crop((max(0,left-pad), max(0,top-pad),
                        min(w,right+pad), min(h,bottom+pad)))
    return pad_to_square(cropped)

def convert_image(img, mode):
    if mode == "pad":   return pad_to_square(img)
    if mode == "crop":  return center_crop(img)
    if mode == "smart": return smart_crop(img)
    raise ValueError(f"Unknown mode: {mode}")


# ─── Safe save (PNG if barcode detected) ─────────────────────────────────────

def safe_save(original: Image.Image, converted: Image.Image,
              out_path: Path, filename: str) -> dict:
    """
    Verify barcode integrity, force PNG for barcode documents,
    save file. Returns verification result dict.
    """
    result = verify(original, converted, filename)

    if not result["ok"]:
        raise BarcodeIntegrityError(result["warning"])

    # Force lossless PNG if barcodes were detected
    if result["original_codes"]:
        out_path = out_path.with_suffix(".png")

    if out_path.suffix.lower() in (".jpg", ".jpeg"):
        converted.save(out_path, format="JPEG", quality=99,
                       subsampling=0)           # max quality, no chroma downsampling
    else:
        converted.save(out_path, format="PNG")

    return result


# ─── File handlers ────────────────────────────────────────────────────────────

def process_raster(src: Path, dst_dir: Path, mode: str) -> list:
    img    = Image.open(src)
    result_img = convert_image(img, mode)
    out    = dst_dir / f"{src.stem}_square{src.suffix.lower()}"
    vr     = safe_save(img, result_img, out, src.name)
    return [(out.with_suffix(".png") if vr["original_codes"] else out, vr)]


def process_pdf(src: Path, dst_dir: Path, mode: str, dpi: int) -> list:
    doc  = fitz.open(str(src))
    zoom = dpi / 72.0
    mat  = fitz.Matrix(zoom, zoom)
    outputs = []

    for i, page in enumerate(doc):
        pix    = page.get_pixmap(matrix=mat, alpha=False)
        img    = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        result_img = convert_image(img, mode)
        suffix = f"_p{i+1:03d}" if len(doc) > 1 else ""
        out    = dst_dir / f"{src.stem}{suffix}_square.png"
        vr     = safe_save(img, result_img, out, f"{src.name} p{i+1}")
        outputs.append((out, vr))

    doc.close()
    return outputs


# ─── Batch runner ─────────────────────────────────────────────────────────────

def batch_convert(input_dir: Path, output_dir: Path,
                  mode="smart", dpi=150, verbose=True) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    if not PYZBAR_AVAILABLE and verbose:
        print("  [!] pyzbar not installed — barcode verification disabled")
        print("      Install: pip install pyzbar\n")

    files = [f for f in sorted(input_dir.iterdir())
             if f.suffix.lower() in SUPPORTED]
    if not files:
        print(f"[!] No supported files in {input_dir}")
        return {"processed": 0, "pages": 0, "errors": []}

    processed, total_pages, errors = 0, 0, []

    for f in files:
        try:
            if f.suffix.lower() == ".pdf":
                outs = process_pdf(f, output_dir, mode, dpi)
            else:
                outs = process_raster(f, output_dir, mode)

            processed   += 1
            total_pages += len(outs)

            if verbose:
                for out_path, vr in outs:
                    img = Image.open(out_path)
                    bc  = "🔲 " + vr["warning"] if vr["original_codes"] else ""
                    print(f"  ✓  {f.name} → {out_path.name}  {img.size[0]}×{img.size[1]}  {bc}")

        except BarcodeIntegrityError as e:
            errors.append((f.name, str(e)))
            print(f"  ✗  BARCODE INTEGRITY FAIL: {e}", file=sys.stderr)
        except Exception as e:
            errors.append((f.name, str(e)))
            print(f"  ✗  {f.name}: {e}", file=sys.stderr)

    if verbose:
        print(f"\n── Done: {processed}/{len(files)} files, {total_pages} pages ──")
        if errors:
            print(f"   ⚠ Integrity errors: {len(errors)}")

    return {"processed": processed, "pages": total_pages, "errors": errors}


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert A4 images to 1:1 square (batch, barcode-safe)",
    )
    parser.add_argument("input_dir",  type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--mode", choices=["pad","crop","smart"], default="smart")
    parser.add_argument("--dpi",  type=int, default=150)
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"[!] Input dir not found: {args.input_dir}")
        sys.exit(1)

    print(f"Mode: {args.mode.upper()} | DPI: {args.dpi}")
    print(f"Input:  {args.input_dir.resolve()}")
    print(f"Output: {args.output_dir.resolve()}\n")

    result = batch_convert(args.input_dir, args.output_dir, args.mode, args.dpi)
    sys.exit(0 if not result["errors"] else 1)


if __name__ == "__main__":
    main()
