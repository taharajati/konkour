"""Paths and model settings. Everything can be overridden with environment variables."""
import os

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.getenv("WORKSPACE", os.path.join(PIPELINE_DIR, "..")))

WORK_DIR = os.getenv("PIPELINE_WORK_DIR", os.path.join(PIPELINE_DIR, "work"))
BANK_ROOT = os.getenv("QUESTIONS_ROOT", os.path.join(WORKSPACE, "question_bank"))
CATALOG = os.getenv("BOOKS_JSON", os.path.join(WORKSPACE, "main books", "books_catalog.json"))
TAXONOMY_DIR = os.getenv("TAXONOMY_DIR", os.path.join(WORKSPACE, "taxonomy"))

# Models. Extraction reads Persian math from page images, the solver checks the key
# independently, tagging picks a concept from a closed list. Keep the solver on a
# strong model: it is the main guard against wrong answer keys.
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "claude-opus-5-5")
SOLVER_MODEL = os.getenv("SOLVER_MODEL", "claude-opus-5-5")
TAG_MODEL = os.getenv("TAG_MODEL", "claude-opus-5-5")
EXTRACT_EFFORT = os.getenv("EXTRACT_EFFORT", "medium")
SOLVER_EFFORT = os.getenv("SOLVER_EFFORT", "high")
TAG_EFFORT = os.getenv("TAG_EFFORT", "low")

RENDER_DPI = int(os.getenv("RENDER_DPI", "200"))

# bump when a prompt changes: cached LLM answers are keyed on it
PROMPT_VERSION = "2026-11-14.1"
