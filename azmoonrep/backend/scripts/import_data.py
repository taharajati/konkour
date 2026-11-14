"""Import books + prepared questions into MongoDB. Run from backend/:
    python -m scripts.import_data ["<path to books_catalog.json>"] ["<path to question_bank root>"]

Defaults are relative to the workspace root (two folders above backend/):
    books:     <workspace>/main books/books_catalog.json
    questions: <workspace>/question_bank
"""
import os
import sys
from app import db
from app.importer import (import_books, import_questions, import_taxonomy,
                          link_concepts_to_chapters, prune_orphan_concepts)

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BOOKS = os.getenv("BOOKS_JSON", os.path.join(WORKSPACE, "main books", "books_catalog.json"))
TAXONOMY = os.getenv("TAXONOMY_DIR", os.path.join(WORKSPACE, "taxonomy"))
QUESTIONS = os.getenv("QUESTIONS_ROOT", os.path.join(WORKSPACE, "question_bank"))

def main():
    books_path = sys.argv[1] if len(sys.argv) > 1 else BOOKS
    questions_path = sys.argv[2] if len(sys.argv) > 2 else QUESTIONS
    if books_path:
        print("books:", import_books(books_path))
    print("taxonomy:", import_taxonomy(TAXONOMY))
    if questions_path:
        print("questions:", import_questions(questions_path))
    print("link:", link_concepts_to_chapters())
    print("prune:", prune_orphan_concepts())

if __name__ == "__main__":
    main()
