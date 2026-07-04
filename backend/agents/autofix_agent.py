from agents.base_agent import BaseAgent

class AutoFixAgent(BaseAgent):
    def fix(self, code: str, issues: list, vulnerabilities: list) -> dict:
        # Prevent key crashes by extracting the problem text safely using .get()
        extracted_vulns = []
        for v in vulnerabilities:
            if isinstance(v, dict):
                extracted_vulns.append(v.get("type") or v.get("issue") or str(v))
            else:
                extracted_vulns.append(str(v))
                
        all_problems = issues + extracted_vulns
        problems_text = "\n".join(f"- {p}" for p in all_problems)

        # Optimized Prompt: Structural template optimized for complex code containment
        system_prompt = """You are a senior systems developer and automation engineer.
        Review the code provided alongside the specific security flaws and structural issues listed.
        
        Refactor the source code completely to repair all defects. Ensure the fix preserves the original
        intended features and uses language-idiomatic safety structures.
        
        Format your response exactly as this JSON object structure:
        {
            "fixed_code": "The complete, refactored, and updated source code goes here as an escaped text string.",
            "changes_made": [
                "Detailed summary item of a resolved defect",
                "Another structural adjustment action"
            ],
            "explanation": "A high-level summary overview explaining why these structural choices were made."
        }"""

        return self.ask_llm_json(
            system_prompt,
            f"REFACTOR TARGET CODE:\n{code}\n\nLIST OF SECURITY & LOGIC PROBLEMS TO REPAIR:\n{problems_text}"
        )

# Quick test
if __name__ == "__main__":
    agent = AutoFixAgent()
    
    bad_code = """
def process_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    db.execute(query)
    """
    
    test_issues = ["Missing type hints"]
    test_vulns = [{"type": "SQL Injection vulnerability through string concatenation"}]
    
    result = agent.fix(bad_code, test_issues, test_vulns)
    
    import pprint
    pprint.pprint(result)
