from typing import TypedDict, Optional, List, Dict, Any

class PipelineState(TypedDict):
    """
    Documents and type-checks the unified state dictionary shared 
    across the Google GenAI SDK workflow pipeline stages.
    """
    # ── Initial Pull Request Inputs ──────────────────────
    pr_title: str
    pr_code: str
    filename: str
    pr_url: str

    # ── Downstream Agent Execution Payloads ──────────────
    review_result: Optional[Dict[str, Any]]
    security_result: Optional[Dict[str, Any]]
    generated_tests: Optional[str]
    fixed_code: Optional[str]
    doc_summary: Optional[str]

    # ── Final Pipeline Output Summaries ──────────────────
    final_summary: Optional[str]
    should_block_merge: bool
    severity_level: str  
    overall_score: int   


def make_initial_state(
    pr_title: str,
    pr_code: str,
    filename: str,
    pr_url: str = ""
) -> PipelineState:
    """Instantiates a structured state instance for a new workflow execution."""
    return {
        "pr_title": pr_title,
        "pr_code": pr_code,
        "filename": filename,
        "pr_url": pr_url,
        "review_result": None,
        "security_result": None,
        "generated_tests": None,
        "fixed_code": None,
        "doc_summary": None,
        "final_summary": None,
        "should_block_merge": False,
        "severity_level": "low",
        "overall_score": 0
    }
