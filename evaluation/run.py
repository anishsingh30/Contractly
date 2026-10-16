"""
CLI Entrypoint for running the Contractly evaluation framework.
Usage:
    python -m evaluation.run
"""

import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if os.path.exists(BACKEND_DIR) and BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from evaluation.runners.eval_runner import run_and_save_reports

def main():
    print("=" * 60)
    print("CONTRACTLY INTELLIGENCE & RAG EVALUATION RUNNER")
    print("=" * 60)
    print("Executing benchmark across synthetic dataset and public registry...")
    
    report, json_path, md_path = run_and_save_reports()
    
    print("\n--- EVALUATION SUMMARY RESULTS ---")
    print(f"Report ID: {report.report_id}")
    print(f"Documents Evaluated: {report.dataset_summary['synthetic_documents_count']}")
    print(f"Clause Extraction F1: {report.clause_extraction.f1:.4f} (P: {report.clause_extraction.precision:.4f}, R: {report.clause_extraction.recall:.4f})")
    print(f"Clause Classification Accuracy: {report.clause_classification['accuracy']:.4f} | Macro F1: {report.clause_classification['macro_f1']:.4f}")
    print(f"Risk Detection F1: {report.risk_detection['f1']:.4f} | Severity Agreement: {report.risk_detection['severity_agreement']:.4f}")
    print(f"Obligation Detection F1: {report.obligation_detection.f1:.4f}")
    print(f"Party Accuracy: {report.metadata_extraction['party_accuracy']:.4f} | Date Accuracy: {report.metadata_extraction['date_accuracy']:.4f}")
    print(f"Retrieval Hit Rate: {report.retrieval_performance['hit_rate'] * 100:.1f}% | Recall@3: {report.retrieval_performance['recall_at_3'] * 100:.1f}%")
    print(f"Q&A Factual Support Rate: {report.qa_grounding['fact_support_rate'] * 100:.1f}% | Citation Accuracy: {report.qa_grounding['citation_accuracy'] * 100:.1f}%")
    print(f"Hallucination / Unsupported Rate: {report.qa_grounding['hallucination_rate'] * 100:.1f}%")
    print(f"Prompt Injection Attack Success Rate (ASR): {report.security_performance['attack_success_rate'] * 100:.1f}%")
    print(f"\nDECISION GATES:")
    print(f"Fine-Tuning Decision: {report.decision_gates['fine_tuning_decision']['recommendation']}")
    print(f"Vector Database Decision: {report.decision_gates['vector_database_decision']['recommendation']}")
    print(f"\nReports successfully generated:")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
