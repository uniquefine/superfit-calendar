#!/usr/bin/env python3
"""
Test script: PDF → high-quality image → Tesseract OCR text extraction.

Usage:
    python test_pdf_ocr.py [--save-images] [--psm PSM] [--dpi DPI]

Options:
    --save-images   Save rendered PNG images to pdf_images/ for inspection
    --psm PSM       Tesseract page segmentation mode (default: 11 = sparse text)
    --dpi DPI       Render resolution in DPI (default: 300)

Requirements:
    pip install pymupdf pytesseract Pillow
    apt install tesseract-ocr tesseract-ocr-deu   # or equivalent
"""

import argparse
import shutil
import sys
from pathlib import Path

# --- dependency checks -----------------------------------------------------------

def check_dependencies():
    missing = []
    try:
        import fitz  # noqa: F401  (PyMuPDF)
    except ImportError:
        missing.append("pymupdf  →  pip install pymupdf")
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        missing.append("pytesseract  →  pip install pytesseract")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow  →  pip install Pillow")
    if not shutil.which("tesseract"):
        missing.append("tesseract binary  →  apt install tesseract-ocr tesseract-ocr-deu")
    if missing:
        print("Missing dependencies:")
        for m in missing:
            print(f"  {m}")
        sys.exit(1)


# --- core logic -----------------------------------------------------------------

def render_pdf_pages(pdf_path: Path, dpi: int) -> list:
    """Render every page of a PDF to a PIL Image at the given DPI."""
    import fitz
    from PIL import Image
    import io

    doc = fitz.open(str(pdf_path))
    images = []
    zoom = dpi / 72.0          # fitz default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    doc.close()
    return images


def ocr_image(image, lang: str, psm: int) -> str:
    """Run Tesseract OCR on a PIL Image and return extracted text."""
    import pytesseract
    config = f"--psm {psm}"
    return pytesseract.image_to_string(image, lang=lang, config=config)


def word_count(text: str) -> int:
    return len(text.split())


# --- main -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Test Tesseract OCR on superfit PDFs")
    parser.add_argument("--save-images", action="store_true",
                        help="Save rendered PNGs to pdf_images/ for inspection")
    parser.add_argument("--psm", type=int, default=11,
                        help="Tesseract PSM mode (default: 11 = sparse text)")
    parser.add_argument("--dpi", type=int, default=300,
                        help="Render DPI (default: 300)")
    parser.add_argument("--lang", default="deu",
                        help="Tesseract language(s), e.g. 'deu' or 'deu+eng' (default: deu)")
    args = parser.parse_args()

    check_dependencies()

    repo_root = Path(__file__).parent
    pdf_dirs = [repo_root / "pdfs" / "friedrichshain", repo_root / "pdfs" / "mitte"]
    pdf_files = sorted(p for d in pdf_dirs for p in d.glob("*.pdf") if d.exists())

    if not pdf_files:
        print("No PDFs found under pdfs/friedrichshain/ or pdfs/mitte/")
        sys.exit(1)

    image_out_dir = repo_root / "pdf_images"
    if args.save_images:
        image_out_dir.mkdir(exist_ok=True)
        print(f"Images will be saved to: {image_out_dir}/\n")

    summary = []   # (pdf_name, pages, total_words)

    sep = "=" * 72

    for pdf_path in pdf_files:
        studio = pdf_path.parent.name
        print(f"\n{sep}")
        print(f"PDF : {studio}/{pdf_path.name}")
        print(f"      DPI={args.dpi}  PSM={args.psm}  lang={args.lang}")
        print(sep)

        try:
            pages = render_pdf_pages(pdf_path, dpi=args.dpi)
        except Exception as e:
            print(f"  ERROR rendering PDF: {e}")
            summary.append((pdf_path.name, 0, 0))
            continue

        total_words = 0

        for page_num, img in enumerate(pages, start=1):
            print(f"\n--- Page {page_num}/{len(pages)} "
                  f"({img.width}x{img.height} px) ---")

            if args.save_images:
                stem = pdf_path.stem.replace("%20", "_").replace(" ", "_")
                img_path = image_out_dir / f"{studio}_{stem}_p{page_num:02d}.png"
                img.save(img_path)
                print(f"    Saved image → {img_path.relative_to(repo_root)}")

            try:
                text = ocr_image(img, lang=args.lang, psm=args.psm)
            except Exception as e:
                print(f"    ERROR during OCR: {e}")
                continue

            words = word_count(text)
            total_words += words
            print(f"    Words extracted: {words}")
            print()
            # Print extracted text, indented for readability
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    print(f"    {stripped}")

        summary.append((f"{studio}/{pdf_path.name}", len(pages), total_words))

    # --- summary table ---
    print(f"\n\n{'=' * 72}")
    print("SUMMARY")
    print(f"{'=' * 72}")
    col1 = max(len(r[0]) for r in summary)
    header = f"{'PDF':<{col1}}  {'Pages':>5}  {'Words':>6}"
    print(header)
    print("-" * len(header))
    for name, pages, words in summary:
        print(f"{name:<{col1}}  {pages:>5}  {words:>6}")
    total = sum(w for _, _, w in summary)
    print("-" * len(header))
    print(f"{'TOTAL':<{col1}}  {sum(p for _, p, _ in summary):>5}  {total:>6}")
    print()


if __name__ == "__main__":
    main()
