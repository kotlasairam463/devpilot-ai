import pprint
from agents.review_agent import ReviewAgent
from agents.security_agent import SecurityAgent
from agents.test_agent import TestAgent
from agents.autofix_agent import AutoFixAgent

sample_code = """
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    result = db.execute(query)
    return result
"""

print("=" * 50)
print("🔍 PHASE 1: Running Diagnostics...")
print("=" * 50)

review = ReviewAgent().review(sample_code, "user.py")
print(f"✅ Review Complete -> Score: {review.get('score')}/10")
print(f"   Issues Found: {review.get('issues')}\n")

security = SecurityAgent().scan(sample_code)
print(f"✅ Security Complete -> Is Safe: {security.get('is_safe')}")
print(f"   Vulnerabilities Tracked: {len(security.get('vulnerabilities', []))}\n")

print("=" * 50)
print("🛠️ PHASE 2: Executing Auto-Fix Workspace...")
print("=" * 50)

issues = review.get("issues", [])
vulnerabilities = security.get("vulnerabilities", [])

fix_results = AutoFixAgent().fix(sample_code, issues, vulnerabilities)
fixed_source_code = fix_results.get("fixed_code", "")

# Safeguard check: If fixed code returns completely blank, fall back to initial source input
if not fixed_source_code or len(fixed_source_code.strip()) == 0:
    print("⚠️ Warning: AutoFixAgent returned an empty code block. Using baseline code.")
    fixed_source_code = sample_code

print("🚀 Refactored Code Generated Successfully!")
print("--- Changes Made ---")
for change in fix_results.get("changes_made", []):
    print(f"- {change}")

print("\n--- Fixed Code Preview ---")
print(fixed_source_code.strip())

print("\n" + "=" * 50)
print("🧪 PHASE 3: Generating Universal Unit Tests...")
print("=" * 50)

tests = TestAgent().generate_tests(fixed_source_code, "user.py")
print("🔥 Unit Tests Generated for Fixed Code:\n")
print(tests.strip())

print("\n" + "=" * 50)
print("🎉 Complete Agent Pipeline Execution Finished! ✅")
print("=" * 50)
