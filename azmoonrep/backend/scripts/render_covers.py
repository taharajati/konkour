"""Render page 1 (cover) of each book PDF to backend/static/books/<book_id>.png"""
import os
import json
import pymupdf

BOOKS_DIR = r"D:/apps/beh/main books"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "books")

catalog = json.load(open(os.path.join(BOOKS_DIR, "books_catalog.json"), encoding="utf-8"))
os.makedirs(OUT_DIR, exist_ok=True)
for b in catalog:
    pdf = os.path.join(BOOKS_DIR, b["file"])
    book_id = b["file"].replace(".pdf", "")
    if not os.path.isfile(pdf):
        print("missing:", pdf)
        continue
    d = pymupdf.open(pdf)
    d[0].get_pixmap(dpi=70).save(os.path.join(OUT_DIR, f"{book_id}.png"))
    print("cover:", book_id)
