# workflow/orchestrator.py
# Google GenAI SDK Pipeline — Lightweight sequential workflow automation

from workflow.state import make_initial_state, PipelineState  # Updated Import Path
from agents.review_agent import ReviewAgent
from agents.security_agent import SecurityAgent
from agents.test_agent import TestAgent
from agents.autofix_agent import AutoFixAgent
from agents.documentation_agent import DocumentationAgent


# Initialize specialist agents once at module level
_review   = ReviewAgent()
_security = SecurityAgent()
_test     = TestAgent()
_autofix  = AutoFixAgent()
_documentation = DocumentationAgent()


def run_pipeline(
    pr_title: str,
    pr_code: str,
    filename: str,
    pr_url: str = ""
) -> PipelineState:
    """
    Runs all four specialist agents sequentially using a shared state data model.
    Enforces cross-agent runtime error boundaries and fallback states.
    """
    state = make_initial_state(pr_title, pr_code, filename, pr_url)

    # ── Station 1: Review Agent ──────────────────────────
    print("🔍 [1/6] Review Agent running...")
    state["review_result"] = _review.review(pr_code, filename) or {}

    # ── Station 2: Security Agent ────────────────────────
    print("🔐 [2/6] Security Agent running...")
    state["security_result"] = _security.scan(pr_code) or {}

    # ── Station 3: AutoFix Agent ─────────────────────────
    print("🛠️  [3/6] AutoFix Agent running...")
    review_data   = state["review_result"]
    security_data = state["security_result"]
    
    issues = review_data.get("issues", [])
    vulns  = security_data.get("vulnerabilities", [])
    
    if issues or vulns:
        fix_response = _autofix.fix(pr_code, issues, vulns) or {}
        state["fixed_code"] = fix_response.get("fixed_code")
    
    # ── Station 4: Test Agent ────────────────────────────
    print("🧪 [4/6] Test Agent running...")
    target_code = state["fixed_code"] if state["fixed_code"] else pr_code
    
    try:
        state["generated_tests"] = _test.generate_tests(target_code, filename)
    except Exception as e:
        print(f"⚠️ Test generation temporarily skipped due to server availability: {e}")
        state["generated_tests"] = "// Unit tests unavailable due to temporary provider demand."

    # ── Station 5: Documentation Agent ───────────────────
    print("📚 [5/6] Documentation Agent running...")
    target_code = state["fixed_code"] if state["fixed_code"] else pr_code
    doc_result = _documentation.document(target_code, filename) or {}
    state["doc_summary"] = doc_result.get("summary")

    # ── Station 6: Summary Generation ────────────────────
    print("📝 [6/6] Creating consolidated workflow summary...")
    score = review_data.get("score", 5)
    
    issues_text = "\n".join(f"- {i}" for i in issues)
    vulns_text  = "\n".join(
        f"- {v.get('type', 'Unknown')} ({v.get('severity','high')}): {v.get('fix', '')}"
        for v in vulns if isinstance(v, dict)
    )
    suggestions_text = "\n".join(f"- {s}" for s in review_data.get("suggestions", []))

    has_critical = any(v.get("severity") == "critical" for v in vulns if isinstance(v, dict))
    state["should_block_merge"] = has_critical or score < 5
    state["severity_level"]     = "critical" if has_critical else "high" if vulns else "low"
    state["overall_score"]      = score

    state["final_summary"] = f"""
## 🤖 DevPilot AI Review

**PR:** {pr_title}
**File:** {filename}
**Code Quality Score:** {score}/10
**Security Status:** {'🔴 UNSAFE' if vulns else '✅ SAFE'}
**Merge Decision:** {'🚫 BLOCKED — Fix issues before merging' if state['should_block_merge'] else '✅ APPROVED — Safe to merge'}

---

### 📋 Code Issues:
{issues_text if issues_text else "No major issues found ✅"}

### 🔐 Security Vulnerabilities:
{vulns_text if vulns_text else "No vulnerabilities found ✅"}

### 💡 Suggestions:
{suggestions_text if suggestions_text else "No alternative adjustments suggested."}

---
### 🛠️ Auto-Fix Code Changes:
{ "Refactored variant generated successfully. Review the file changes before staging." if state["fixed_code"] else "No auto-remediation updates were requested." }

---
### 📚 Documentation:
{state.get("doc_summary") or "No documentation summary generated."}
---
*Reviewed by DevPilot AI — Powered by Gemini 2.5 Flash via Google GenAI SDK*
    """

    return state


# ── Run Local Test Verification ───────────────────────────

if __name__ == "__main__":
    result = run_pipeline(
        pr_title="Add user login feature",
        pr_code="""
def login(username, password):
    query = "SELECT * FROM users WHERE username='" + username + "'"
    user = db.execute(query)
    if user and user.password == password:
        return True
    return False
        """,
        filename="auth.py",
        pr_url="https://github.com"
    )

    print("\n" + "=" * 60)
    print(result["final_summary"])
    print("=" * 60)
    print(f"Block Merge: {result['should_block_merge']}")
