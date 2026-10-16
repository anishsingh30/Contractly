import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if os.path.exists(BACKEND_DIR) and BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from evaluation.runners.eval_runner import EvaluationRunner, run_and_save_reports, generate_markdown_report
from evaluation.schemas.eval_schema import EvaluationReport, EvaluationDocument

__all__ = [
    "EvaluationRunner",
    "run_and_save_reports",
    "generate_markdown_report",
    "EvaluationReport",
    "EvaluationDocument"
]
