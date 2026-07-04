from agents.base_agent import BaseAgent

class DocumentationAgent(BaseAgent):
    def document(self, code: str, filename: str) -> dict:
        system_prompt = """You are a technical writer. Given source code, write a plain-English summary.

        Format your response exactly as this JSON object template:
        {
            "summary": "2-3 sentence summary of what this code does and why"
        }"""
        return self.ask_llm_json(system_prompt, f"Summarize this code from {filename}:\n\n{code}")