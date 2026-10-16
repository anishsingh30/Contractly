import os
import json
import pytest
from evaluation.datasets.public_registry import get_public_datasets_summary, PUBLIC_DATASETS_REGISTRY
from evaluation.datasets.synthetic_dataset import get_synthetic_dataset, SYNTHETIC_EVALUATION_DATASET
from evaluation.schemas.eval_schema import EvaluationDocument, EvaluationReport, MetricScore
from evaluation.metrics.eval_calculators import (
    token_overlap_ratio,
    is_clause_match,
    compute_clause_extraction_metrics,
    compute_retrieval_metrics,
    compute_security_metrics
)
from evaluation.runners.eval_runner import EvaluationRunner, run_and_save_reports


def test_1_public_dataset_registry_completeness():
    """Verify public datasets registry includes CUAD, ContractNLI, Atticus, and LEDGAR."""
    summary = get_public_datasets_summary()
    assert len(summary) >= 4
    names = [ds["name"] for ds in summary]
    assert any("CUAD" in n for n in names)
    assert any("ContractNLI" in n for n in names)
    assert any("Atticus" in n for n in names)
    assert any("LEDGAR" in n for n in names)

    for ds in summary:
        assert "license" in ds and bool(ds["license"])
        assert "source" in ds and bool(ds["source"])
        assert "tasks" in ds and len(ds["tasks"]) > 0
        assert "document_count" in ds and ds["document_count"] > 0
        assert "fields_used_in_benchmark" in ds and len(ds["fields_used_in_benchmark"]) > 0


def test_2_synthetic_dataset_has_all_20_required_scenarios():
    """Verify synthetic dataset contains all 20 required contract scenarios."""
    docs = get_synthetic_dataset()
    assert len(docs) == 20

    scenario_tags = [d.scenario_tag for d in docs]
    required_tags = [
        "UNCAPPED_LIABILITY",
        "CAPPED_LIABILITY",
        "BROAD_INDEMNIFICATION",
        "MUTUAL_INDEMNIFICATION",
        "AUTOMATIC_RENEWAL",
        "MISSING_RENEWAL_PROTECTION",
        "SHORT_PAYMENT_TERMS",
        "LONG_PAYMENT_TERMS",
        "UNILATERAL_TERMINATION",
        "TERMINATION_FOR_CONVENIENCE",
        "DATA_USAGE_CONCERN",
        "CONFIDENTIALITY_OBLIGATION",
        "AMBIGUOUS_OBLIGATION",
        "CLEAR_OBLIGATION",
        "UNUSUAL_GOVERNING_LAW",
        "ASSIGNMENT_WITHOUT_CONSENT",
        "MISSING_INSURANCE_REQUIREMENT",
        "NON_COMPETE_RESTRICTION",
        "IP_OWNERSHIP_CLAUSE",
        "MISSING_TERMINATION_PROTECTION"
    ]
    for tag in required_tags:
        assert tag in scenario_tags, f"Missing required scenario tag: {tag}"


def test_3_evaluation_schemas_validation():
    """Verify evaluation document schema validates fields and types."""
    doc = SYNTHETIC_EVALUATION_DATASET[0]
    assert isinstance(doc, EvaluationDocument)
    assert doc.document_id.startswith("SYN-")
    assert len(doc.clauses) > 0
    assert len(doc.parties) > 0
    assert len(doc.qa_pairs) > 0


def test_4_metric_calculators_unit():
    """Unit tests for token overlap, span match, and metric calculations."""
    t1 = "Neither party shall be liable for indirect damages."
    t2 = "Neither party will be liable for consequential or indirect damages."
    ratio = token_overlap_ratio(t1, t2)
    assert ratio > 0.4
    assert is_clause_match(t1, t2)

    # Security ASR unit test
    class DummyDoc:
        document_id = "DUMMY-1"
        injections = [
            type("Inj", (), {
                "attack_id": "inj-1",
                "malicious_text": "ignore instructions",
                "forbidden_outputs": ["PWNED"]
            })()
        ]

    # Non-breached injection
    res_clean, failures_clean = compute_security_metrics(
        [DummyDoc()],
        {"DUMMY-1:inj-1": {"output": "Standard contractual clause."}}
    )
    assert res_clean["attack_success_rate"] == 0.0
    assert len(failures_clean) == 0

    # Breached injection
    res_breach, failures_breach = compute_security_metrics(
        [DummyDoc()],
        {"DUMMY-1:inj-1": {"output": "System PWNED successfully."}}
    )
    assert res_breach["attack_success_rate"] == 1.0
    assert len(failures_breach) == 1
    assert failures_breach[0].failure_type == "PROMPT_INJECTION_FAILURE"


def test_5_evaluation_runner_execution():
    """Verify full EvaluationRunner executes without error and computes all metrics."""
    runner = EvaluationRunner(use_live_gemini_if_available=False)
    report = runner.execute_evaluation()

    assert isinstance(report, EvaluationReport)
    assert report.dataset_summary["synthetic_documents_count"] == 20
    assert report.clause_extraction.recall > 0.8
    assert report.clause_classification["accuracy"] > 0.7
    assert report.retrieval_performance["hit_rate"] >= 0.85
    assert report.security_performance["attack_success_rate"] == 0.0


def test_6_failure_analysis_categorization():
    """Verify that failure analysis groups diagnostic items properly."""
    runner = EvaluationRunner(use_live_gemini_if_available=False)
    report = runner.execute_evaluation()

    assert isinstance(report.failures, list)
    valid_failure_types = {
        "MISSED_CLAUSE",
        "WRONG_CATEGORY",
        "FALSE_RISK",
        "MISSED_RISK",
        "WRONG_SEVERITY",
        "MISSED_OBLIGATION",
        "WRONG_DATE",
        "WRONG_PARTY",
        "RETRIEVAL_MISS",
        "WRONG_CITATION",
        "UNSUPPORTED_ANSWER",
        "PROMPT_INJECTION_FAILURE"
    }
    for f in report.failures:
        assert f.failure_type in valid_failure_types
        assert bool(f.document_id)
        assert bool(f.detail)


def test_7_reports_generation_json_and_markdown(tmp_path):
    """Verify JSON and Markdown reports are saved and formatted correctly."""
    report, json_path, md_path = run_and_save_reports(output_dir=str(tmp_path))

    assert os.path.exists(json_path)
    assert os.path.exists(md_path)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "clause_extraction" in data
        assert "retrieval_performance" in data
        assert "decision_gates" in data

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
        assert "# CONTRACTLY INTELLIGENCE & RAG EVALUATION REPORT" in md_text
        assert "Decision Gates" in md_text
        assert "Hit Rate" in md_text


def test_8_decision_gates_logic():
    """Verify decision gates are reasoned and output valid recommendation values."""
    runner = EvaluationRunner(use_live_gemini_if_available=False)
    report = runner.execute_evaluation()

    gates = report.decision_gates
    assert "fine_tuning_decision" in gates
    assert "vector_database_decision" in gates
    assert gates["fine_tuning_decision"]["recommendation"] in ("YES", "NO", "POSSIBLY")
    assert gates["vector_database_decision"]["recommendation"] in ("YES", "NO", "POSSIBLY")
    assert len(gates["fine_tuning_decision"]["justification"]) > 20
    assert len(gates["vector_database_decision"]["justification"]) > 20
