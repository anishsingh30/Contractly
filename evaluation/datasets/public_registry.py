"""
Public Contract Datasets Registry and Assessment.
Records public datasets evaluated for contract intelligence research, benchmarking, and evaluation.
"""

from typing import List, Dict, Any

PUBLIC_DATASETS_REGISTRY: List[Dict[str, Any]] = [
    {
        "name": "CUAD (Contract Understanding Atticus Dataset)",
        "source": "The Atticus Project / NeurIPS 2021 (https://github.com/TheAtticusProject/cuad)",
        "license": "CC BY 4.0 (Creative Commons Attribution 4.0 International)",
        "tasks": [
            "Contract Clause Extraction",
            "Contract Review Classification",
            "Entity/Party Identification",
            "Question Answering"
        ],
        "document_count": 510,
        "annotation_count": 13110,
        "categories_covered": 41,
        "fields_used_in_benchmark": [
            "Document Text",
            "Category Label (e.g., Limitation of Liability, Termination for Convenience, Non-Compete, Governing Law)",
            "Extracted Clause Span (start/end character offsets)",
            "Answers to SQuAD-formatted Question Prompts"
        ],
        "suitability_for_contractly": (
            "Permissible for benchmark evaluation and validation. Commercial use permitted under CC BY 4.0 with attribution. "
            "Not bundled into production runtime to prevent repository bloat; used as reference benchmark schema."
        ),
        "licensing_status": "Approved for evaluation and non-exclusive research/commercial use with attribution."
    },
    {
        "name": "ContractNLI (Document-level Natural Language Inference for Contracts)",
        "source": "Stanford / NAACL 2022 (https://github.com/stanford-nlp/contract-nli)",
        "license": "CC BY 4.0",
        "tasks": [
            "Document-level NLI",
            "Contract Hypothesis Verification",
            "Evidence Grounding / Span Identification"
        ],
        "document_count": 607,
        "annotation_count": 10319,
        "categories_covered": 17,
        "fields_used_in_benchmark": [
            "Full NDA Document Text",
            "Hypothesis Questions (e.g., 'Explicit permission required to disclose confidential information')",
            "NLI Label: Entailment, Contradiction, Neutral",
            "Evidence Spans (Exact grounding sentences in document)"
        ],
        "suitability_for_contractly": (
            "Highly aligned with Contractly Grounded Q&A and RAG evaluation. "
            "Validates whether contract text supports, contradicts, or leaves unverified a user proposition."
        ),
        "licensing_status": "Approved for evaluation with attribution."
    },
    {
        "name": "Atticus Open Contracts (AOC)",
        "source": "The Atticus Project (https://www.atticusprojectai.org/open-contracts)",
        "license": "CC BY 4.0",
        "tasks": [
            "Commercial Contract Metadata Parsing",
            "Preamble & Recital Entity Extraction",
            "Renewal & Expiration Date Detection"
        ],
        "document_count": 1200,
        "annotation_count": 28000,
        "categories_covered": 35,
        "fields_used_in_benchmark": [
            "Effective Date",
            "Counterparties / Contracting Entities",
            "Governing Law / Jurisdiction",
            "Payment Term Clauses"
        ],
        "suitability_for_contractly": (
            "Used to design realistic date/party normalization fixtures and evaluate deterministic metadata extraction."
        ),
        "licensing_status": "Approved for evaluation with attribution."
    },
    {
        "name": "LEDGAR (Legal Document Clause Classification)",
        "source": "Tuggener et al., LREC 2020 / Hugging Face datasets",
        "license": "MIT License",
        "tasks": [
            "Clause Taxonomy Categorization",
            "Multi-class Provision Classification"
        ],
        "document_count": 60540,
        "annotation_count": 84627,
        "categories_covered": 100,
        "fields_used_in_benchmark": [
            "Provision Text",
            "Standardized Clause Label (e.g., Severability, Termination, Indemnification)"
        ],
        "suitability_for_contractly": (
            "Reference taxonomy for validating Contractly's 26 standard clause categories against SEC EDGAR distributions."
        ),
        "licensing_status": "Approved under permissive MIT License."
    }
]

def get_public_datasets_summary() -> List[Dict[str, Any]]:
    """Returns registry summary of public datasets."""
    return PUBLIC_DATASETS_REGISTRY
