"""Figure extraction from the PDF's vector data (no model, no pixel guessing).

    python -m pipeline figures <pdf> <bank folder> [--apply]

For every question strip on a page it finds the vector drawings that belong to a
diagram (black strokes, grey fills), ignoring the page furniture (table rules, the pink
option badges). The diagram is rendered straight from the PDF at high resolution, with
the labels next to it (A, B, √5 ...).

Two shapes of result:
  stem figure      one image shown under the question text
  option figures   the four options ARE diagrams (one under each option badge): one
                   image per option, in printed order (right to left)

Without --apply it only reports and writes previews to work/<pdf>/figures_preview/.
With --apply it replaces the figure files in the bank folders (old files are moved to
work/<pdf>/figures_backup/) and updates meta.json and question.md.
"""
import json
import os
import re
import shutil

import pymupdf

from .pdfwork import load_json, save_json

ZOOM = 3.0            # 216 dpi
PAD = 5               # points around a figure
LABEL_REACH = 16      # points: short labels this close to a diagram belong to it
GROUP_GAP = 22        # points of empty space that separates two diagrams
IMG_MD = re.compile(r"\n*!\[[^\]]*\]\([^)]*\)\n*")


def _grey(c) -> bool:
    return c is not None and abs(c[0] - c[1]) < 0.03 and abs(c[1] - c[2]) < 0.03


def _pink(c) -> bool:
    return c is not None and c[0] > 0.7 and c[0] - c[1] > 0.2


def _strips(page) -> list:
    """(number, y0, y1) for each question row: between wide rules, numbered in the margin"""
    W = page.rect.width
    wide = [d["rect"] for d in page.get_drawings() if d["rect"].width > W * 0.5]
    # a question row is either a drawn box, or the space between two thin rules
    boxes = [r for r in wide if r.height > 20 and r.x0 > 1]
    left = min((r.x0 for r in boxes), default=0)     # left edge of the question table
    rows = [(r.y0, r.y1) for r in boxes]
    rules = sorted({round(r.y0, 1) for r in wide if r.height < 3})
    rows += list(zip(rules, rules[1:]))
    nums = [(w[1], int(w[4])) for w in page.get_text("words")
            if w[0] > W * 0.9 and w[4].isdigit()]
    out, seen = [], set()
    for y0, y1 in sorted(rows, key=lambda t: t[1] - t[0]):     # smallest row that fits wins
        n = [v for y, v in nums if y0 <= y < y1]
        if len(n) == 1 and y1 - y0 > 20 and n[0] not in seen:
            seen.add(n[0])
            out.append((n[0], y0, y1, left))
    return sorted(out)


def _union(rects):
    r = pymupdf.Rect(rects[0])
    for x in rects[1:]:
        r |= x
    return r


def _cluster(shapes, gap: float) -> list:
    """connected groups: shapes closer than `gap` (in both directions) belong together"""
    groups = []
    for r in shapes:
        box = pymupdf.Rect(r)
        while True:
            near = next((g for g in groups if _gap(g, box) <= gap), None)
            if near is None:
                break
            groups.remove(near)
            box |= near
        groups.append(box)
    return groups


def _find(page, y0: float, y1: float, x0: float = 0, tight: bool = False):
    """returns (figure groups, badge rects) inside one strip"""
    W = page.rect.width
    # inside the table only: page decorations in the margins are not figures
    strip = pymupdf.Rect(x0 + 1, y0 + 1, W * 0.905, y1 - 1)
    badges, ink = [], []
    for d in page.get_drawings():
        r = d["rect"]
        if not strip.contains(r):
            continue
        if _pink(d.get("fill")):
            badges.append(r)
            continue
        ink.append((r, d))
    badge_boxes = [b + (-2, -2, 2, 2) for b in badges]
    shapes = []
    for r, d in ink:
        if any(b.contains(r) for b in badge_boxes):
            continue                                          # the digit inside a badge
        if r.width < 2 and r.height > (y1 - y0) * 0.8:
            continue                                          # cell border
        if r.width > W * 0.5 and r.height < 3:
            continue                                          # rule
        stroke, fill = d.get("color"), d.get("fill")
        if not ((stroke is not None and _grey(stroke)) or (fill is not None and _grey(fill))):
            continue
        if fill is not None and fill[0] > 0.97 and stroke is None:
            continue                                          # white patch
        if r.width < 1.5 and r.height < 1.5:
            continue
        shapes.append(r)
    # drop text-like marks: underlines of the stem (thin, long, flat)
    shapes = [r for r in shapes if not (r.height < 1.2 and r.width > 12)]
    if not shapes:
        return [], badges
    if tight:
        # diagrams stacked under each other (option grids): split in both directions
        boxes = _cluster(shapes, 3)
    else:
        # group by horizontal gaps
        shapes.sort(key=lambda r: r.x0)
        groups, cur = [], [shapes[0]]
        for r in shapes[1:]:
            if r.x0 - max(x.x1 for x in cur) > GROUP_GAP:
                groups.append(cur); cur = [r]
            else:
                cur.append(r)
        groups.append(cur)
        boxes = [_union(g) for g in groups]
    boxes = [b for b in boxes if b.width > 14 and b.height > 14]   # not a stray mark
    # labels: short words close to a diagram (A, B, 5, x ...), not Persian sentences
    words = [pymupdf.Rect(w[:4]) for w in page.get_text("words")
             if strip.contains(pymupdf.Rect(w[:4])) and len(w[4]) <= 4
             and not re.search(r"[؀-ۿ]{3,}", w[4])]
    out = []
    for b in boxes:
        lr = 4 if tight else LABEL_REACH
        reach = b + (-lr, -lr, lr, lr)
        for w in words:
            if reach.contains(w) and not any(bb.intersects(w) for bb in badge_boxes):
                b |= w
        pad = 2 if tight else PAD
        b = (b + (-pad, -pad, pad, pad)) & strip
        for bb in badge_boxes:                                # never show a piece of a badge
            if not bb.intersects(b):
                continue
            # cut the box on the side that loses the least of the diagram
            cuts = {"top": bb.y1 - b.y0, "bottom": b.y1 - bb.y0,
                    "left": bb.x1 - b.x0, "right": b.x1 - bb.x0}
            side = min(cuts, key=cuts.get)
            if side == "top":
                b.y0 = bb.y1 + 1
            elif side == "bottom":
                b.y1 = bb.y0 - 1
            elif side == "left":
                b.x0 = bb.x1 + 1
            else:
                b.x1 = bb.x0 - 1
        out.append(b)
    return out, badges


def _merge_badges(badges) -> list:
    """badge shapes come in nested layers: merge the overlapping ones"""
    merged = []
    for b in badges:
        b = pymupdf.Rect(b)
        while True:
            hit = next((m for m in merged if m.intersects(b)), None)
            if hit is None:
                break
            merged.remove(hit)
            b |= hit
        merged.append(b)
    return merged


def _gap(a, b) -> float:
    dx = max(0, a.x0 - b.x1, b.x0 - a.x1)
    dy = max(0, a.y0 - b.y1, b.y0 - a.y1)
    return (dx * dx + dy * dy) ** 0.5


def _option_figures(boxes, badges):
    """if the diagrams are the options themselves (each one next to or under an option
    badge), return them in printed option order (rows top to bottom, right to left),
    with None for an option that is plain text. Otherwise None."""
    merged = _merge_badges(badges)
    if len(merged) != 4 or len(boxes) < 2:
        return None
    merged.sort(key=lambda r: (round(r.y0 / 12), -r.x0))
    owner = {}
    for box in boxes:
        d, i = min((_gap(box, m), i) for i, m in enumerate(merged))
        if d > 40 or i in owner:
            return None                       # a diagram that belongs to no single option
        owner[i] = box
    return [owner.get(i) for i in range(4)]

def extract(pdf_path: str) -> dict:
    """{printed number: {"kind": "stem"|"options", "page": n, "boxes": [Rect...]}}"""
    doc = pymupdf.open(pdf_path)
    found, seen = {}, set()
    for page in doc:
        strips = _strips(page)
        if any(n in seen for n, *_ in strips):
            break            # numbers start again: this is the answer section, not questions
        seen |= {n for n, *_ in strips}
        for num, y0, y1, x0 in strips:
            boxes, badges = _find(page, y0, y1, x0)
            if not boxes:
                continue
            per_option = _option_figures(boxes, badges)
            if len(_merge_badges(badges)) == 4:
                tight_boxes, _ = _find(page, y0, y1, x0, tight=True)
                alt = _option_figures(tight_boxes, badges)
                count = lambda p: sum(b is not None for b in p) if p else 0   # noqa: E731
                if count(alt) > count(per_option):
                    per_option = alt
            if per_option:
                found[num] = {"kind": "options", "page": page.number, "boxes": per_option}
            else:
                found[num] = {"kind": "stem", "page": page.number, "boxes": [_union(boxes)]}
    return found


def render(doc, page_no: int, box, path: str) -> None:
    pix = doc[page_no].get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=box, alpha=False)
    pix.save(path)


def run(pdf_path: str, bank_folder: str, work: str, apply: bool, log=print) -> dict:
    doc = pymupdf.open(pdf_path)
    found = extract(pdf_path)
    preview = os.path.join(work, "figures_preview")
    backup = os.path.join(work, "figures_backup")
    os.makedirs(preview, exist_ok=True)
    by_number = {}
    for name in sorted(os.listdir(bank_folder)):
        meta = load_json(os.path.join(bank_folder, name, "meta.json"))
        if meta and meta.get("printed_question_number"):
            by_number[meta["printed_question_number"]] = (name, meta)

    report = {"stem": [], "options": [], "lost": [], "new": [], "no_folder": []}
    for num, f in sorted(found.items()):
        if num not in by_number:
            report["no_folder"].append(num); continue
        name, meta = by_number[num]
        files = ["figure.png"] if f["kind"] == "stem" else \
            [f"option{i}.png" if b is not None else None for i, b in enumerate(f["boxes"], start=1)]
        for box, fn in zip(f["boxes"], files):
            if fn:
                render(doc, f["page"], box, os.path.join(preview, f"{name}_{fn}"))
        report[f["kind"]].append(name)
        if not meta.get("figures") and not meta.get("option_figures"):
            report["new"].append(name)
        if not apply:
            continue
        folder = os.path.join(bank_folder, name)
        if meta.get("locked"):
            continue
        for old in list(meta.get("figures") or []) + list(meta.get("option_figures") or []):
            src = os.path.join(folder, old or "-")
            if os.path.isfile(src):
                os.makedirs(os.path.join(backup, name), exist_ok=True)
                shutil.move(src, os.path.join(backup, name, old))
        for fn in filter(None, files):
            shutil.copy2(os.path.join(preview, f"{name}_{fn}"), os.path.join(folder, fn))
        meta["figures"] = files if f["kind"] == "stem" else []
        meta["option_figures"] = files if f["kind"] == "options" else []
        meta["figure_source"] = "pdf_vector"
        save_json(os.path.join(folder, "meta.json"), meta)
        qmd = os.path.join(folder, "question.md")
        if os.path.isfile(qmd):
            with open(qmd, encoding="utf-8") as fh:
                text = fh.read()
            text = IMG_MD.sub("\n\n", text)                  # figures live in meta.json only
            with open(qmd, "w", encoding="utf-8") as fh:
                fh.write(text)
    for num, (name, meta) in by_number.items():
        if (meta.get("figures") or meta.get("option_figures")) and num not in found \
                and meta.get("figure_source") != "pdf_vector":
            report["lost"].append(name)       # bank says "has a figure", the PDF scan found none
    save_json(os.path.join(work, "figures_report.json"), report)
    log(json.dumps({k: len(v) for k, v in report.items()}))
    return report
