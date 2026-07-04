from agents.base_agent import BaseAgent

class ReviewAgent(BaseAgent):
    def review(self, code: str, filename: str) -> dict:
        # Re-adding the structural template directly in the system prompt
        system_prompt = """You are a senior software engineer doing code review across multiple
        programming languages. Detect the language from the code and filename provided, and apply
        the conventions and best practices appropriate to that language.
        
        Format your response exactly as this JSON object structure:
        {
            "score": 7,
            "issues": ["No error handling", "Variable names unclear"],
            "suggestions": ["Add try/except", "Use descriptive names"],
            "complexity": "low/medium/high",
            "summary": "One line summary of the code quality"
        }"""

        return self.ask_llm_json(
            system_prompt,
            f"Review this code from file {filename}:\n\n{code}"
        )
