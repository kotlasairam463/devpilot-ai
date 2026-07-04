from agents.base_agent import BaseAgent

class SecurityAgent(BaseAgent):
    def scan(self, code: str) -> dict:
        # Optimized Prompt: Focused entirely on security rules and the clean data template
        system_prompt = """You are an expert cybersecurity engineer reviewing multi-language source code. 
        Analyze the language conventions and apply relevant secure coding standards (like OWASP Top 10).
        
        Identify all code defects, exposed secrets, and security vulnerabilities.
        
        Format your response exactly as this JSON object template:
        {
            "is_safe": false,
            "risk_score": 8,
            "vulnerabilities": [
                {
                    "type": "Vulnerability Name",
                    "severity": "critical/high/medium/low",
                    "line": "the exact vulnerable code statement",
                    "fix": "Specific, actionable remediation instruction"
                }
            ]
        }"""

        return self.ask_llm_json(
            system_prompt,
            f"Perform a deep security scan on this code block:\n\n{code}"
        )

# Quick test
if __name__ == "__main__":
    agent = SecurityAgent()
    result = agent.scan("""
api_key = "sk-abc123secret"
password = "admin123"
query = "SELECT * FROM users WHERE id=" + user_id
    """)
    
    import pprint
    pprint.pprint(result)
