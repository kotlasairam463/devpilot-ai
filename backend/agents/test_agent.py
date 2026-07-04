from agents.base_agent import BaseAgent

class TestAgent(BaseAgent):
    def generate_tests(self, code: str, filename: str) -> str:
        # Strict guidelines to make sure the agent adapts flawlessly to any language
        system_prompt = """You are a senior, multi-language software test engineer.
        Analyze the provided filename extension to detect the programming language, and apply 
        the exact idiom, testing conventions, and framework syntax native to that ecosystem.
        
        FRAMEWORK SELECTOR RULE:
        - Python: Use `pytest` (independent functions, native assert statements)
        - JavaScript / TypeScript: Use the native `node:test` and `node:assert` runner 
        - Go: Use native `testing` library (`func TestXxx(t *testing.T)`)
        - Rust: Use native conditional compilation testing hooks (`#[cfg(test)]`)
        - Java: Use `JUnit 5`
        - C#: Use `xUnit`
        - Other: Use the most dominant, modern standard industry framework for that language.
        
        TESTING COVERAGE EXPECTATIONS:
        1. Success Scenarios: Validate expected behaviors using ideal inputs.
        2. Structural Boundaries: Test empty limits, zero arrays, null pointers, and negative values.
        3. Exception Propagation: Ensure functions raise proper errors on catastrophic fault inputs.
        
        STRICT OUTPUT FORMAT RULES:
        Return RAW executable test code block strings only.
        Do not use markdown backticks or wrappers (DO NOT wrap with ``` or ```python).
        Do not include explanations, comments explaining code, introduction text, or summaries."""

        return self.ask_llm(
            system_prompt,
            f"Generate an isolated test suite matching the filename {filename} for this code:\n\n{code}"
        )

# Quick multi-language verification tests
if __name__ == "__main__":
    agent = TestAgent()
    
    # Test 1: Python Component
    print("🐍 --- Generating Python Tests ---")
    py_code = "def divide(a, b):\n    return a / b"
    print(agent.generate_tests(py_code, "math_utils.py"))
    
    print("\n" + "="*40 + "\n")
    
    # Test 2: JavaScript Component (Will output modern native node:test code)
    print("🟨 --- Generating JavaScript Tests ---")
    js_code = "function greet(name) {\n    return `Hello, ${name}!`;\n}"
    print(agent.generate_tests(js_code, "greeting.js"))
