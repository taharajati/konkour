"""PDF -> page images -> question blocks.

Block detection generalizes the pilot's `strip_crop`: question tables in these exam
PDFs are separated by long horizontal rules. A row counts as a rule when it holds one
long unbroken dark run (text rows are fragmented, rules are not), so it needs no
per-PDF thresholds or page coordinates. Pages without rules become one block; the
extraction prompt handles several questions in one image either way.
"""
import io
import json
import os

import numpy as np
import pymupdf
from PIL import Image


def render_pages(pdf_path: str, out_dir: str, dpi: int) -> list:
    os.makedirs(out_dir, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, start=1):
        png = os.path.join(out_dir, f"p{i:03d}.png")
        if not os.path.isfile(png):
            page.get_pixmap(dpi=dpi).save(png)
        pages.append({"page": i, "file": png, "text_chars": len(page.get_text().strip())})
    return pages


def _longest_dark_run(row: np.ndarray) -> int:
    if not row.any():
        return 0
    padded = np.concatenate(([False], row, [False])).astype(np.int8)
    d = np.diff(padded)
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
    return int((ends - starts).max())


def find_rules(gray: np.ndarray, min_frac: float = 0.4, dark: int = 120) -> list:
    """y centers of long horizontal rules"""
    h, w = gray.shape
    mask = gray < dark
    rows = [y for y in range(h) if _longest_dark_run(mask[y]) >= min_frac * w]
    lines, start, prev = [], None, None
    for y in rows:
        if start is None:
            start = prev = y
        elif y - prev <= 3:
            prev = y
        else:
            lines.append((start + prev) // 2); start = prev = y
    if start is not None:
        lines.append((start + prev) // 2)
    return lines


def _rule_x_extent(gray: np.ndarray, y: int, dark: int = 120):
    xs = np.where(gray[y] < dark)[0]
    return (int(xs.min()), int(xs.max())) if len(xs) else (0, gray.shape[1] - 1)


def detect_blocks(page_png: str, min_height_frac: float = 0.02) -> list:
    img = Image.open(page_png).convert("L")
    gray = np.asarray(img)
    h, w = gray.shape
    lines = find_rules(gray)
    blocks = []
    for a, b in zip(lines, lines[1:]):
        if b - a < min_height_frac * h:
            continue
        x0, x1 = _rule_x_extent(gray, a)
        blocks.append([max(0, x0 - 4), max(0, a - 4), min(w, x1 + 5), min(h, b + 5)])
    covered = sum(b[3] - b[1] for b in blocks)
    if len(blocks) < 2 or covered < 0.35 * h:
        return [[0, 0, w, h]]          # no table structure: whole page is one block
    return blocks


def group_boxes(boxes: list, page_h: int, max_frac: float) -> list:
    """merge neighbouring boxes into chunks up to max_frac of the page height:
    fewer, larger images per LLM call, and a question split by a rule stays together"""
    groups, cur = [], None
    for b in boxes:
        if cur and (b[3] - cur[1]) <= max_frac * page_h:
            cur = [min(cur[0], b[0]), cur[1], max(cur[2], b[2]), b[3]]
        else:
            if cur:
                groups.append(cur)
            cur = list(b)
    if cur:
        groups.append(cur)
    return groups


def cut_blocks(pages: list, out_dir: str, max_frac: float = 0.45) -> list:
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for p in pages:
        img = Image.open(p["file"])
        boxes = group_boxes(detect_blocks(p["file"]), img.size[1], max_frac)
        for j, box in enumerate(boxes, start=1):
            bid = f"p{p['page']:03d}_b{j:02d}"
            path = os.path.join(out_dir, f"{bid}.png")
            if not os.path.isfile(path):
                img.crop(tuple(box)).save(path)
            out.append({"id": bid, "page": p["page"], "bbox": box, "file": path,
                        "whole_page": len(boxes) == 1})
    return out


def crop_fraction(png_path: str, frac_box: list) -> bytes:
    """crop a [x0,y0,x1,y1] box given as fractions (0..1) of the image, as PNG bytes"""
    img = Image.open(png_path)
    w, h = img.size
    x0, y0, x1, y1 = frac_box
    box = (max(0, int(x0 * w) - 6), max(0, int(y0 * h) - 6),
           min(w, int(x1 * w) + 6), min(h, int(y1 * h) + 6))
    buf = io.BytesIO()
    img.crop(box).save(buf, format="PNG")
    return buf.getvalue()


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_json(path: str, default=None):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)
