import os
import json
import time  # Imported for cooldown delays
from google import genai
from google.genai import types
from google.genai.errors import APIError  # 💡 CRITICAL: Import the official error handler
from dotenv import load_dotenv

load_dotenv()

class BaseAgent:
    def __init__(self):
        self.is_production = os.getenv("PROD_ENV", "false").lower() == "true"
        
        if self.is_production:
            self.client = genai.Client(
                vertexai=True,
                project=os.getenv("GCP_PROJECT_ID"),
                location=os.getenv("GCP_LOCATION", "us-central1")
            )
            self.model_name = "gemini-3.5-pro"
        else:
            self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            self.model_name = "gemini-3.5-flash"
            
        
        self.config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192,
        )

    def ask_llm(self, system_prompt: str, user_message: str, retries: int = 3, delay: int = 4) -> str:
        """Send a prompt to Gemini with explicit APIError recovery loops"""
        config_with_system = types.GenerateContentConfig(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
            system_instruction=system_prompt
        )
        
        # ── Handle API Errors via a Retry Loop ───────────────────
        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=user_message,
                    config=config_with_system
                )
                return response.text
                
            except APIError as e:  # 🎯 Catch explicit Google API faults
                # Catch 429 (Rate Limit Exhausted) or 503 (Server Overload/Spikes)
                if e.code in [429, 503] and attempt < retries - 1:
                    print(f"⚠️ API Status {e.code} caught. Cooldown for {delay}s... (Retry {attempt+1}/{retries})")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff (4s -> 8s -> 16s)
                    continue
                print(f"❌ Catastrophic API Error [{e.code}]: {e.message}")
                raise e  # Bubble up the error if we exhaust all retries
                
            except Exception as e:  # Catch general Python runtime errors
                print(f"❌ System Exception in ask_llm: {e}")
                raise e

    def ask_llm_json(self, system_prompt: str, user_message: str, retries: int = 3, delay: int = 4) -> dict:
        """Send a prompt forcing strict JSON format with explicit APIError recovery loops"""
        json_config = types.GenerateContentConfig(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
            system_instruction=system_prompt,
            response_mime_type="application/json"
        )
        
        # ── Handle API Errors via a Retry Loop ───────────────────
        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=user_message,
                    config=json_config
                )
                return json.loads(response.text)
                
            except APIError as e:  # 🎯 Catch explicit Google API faults
                if e.code in [429, 503] and attempt < retries - 1:
                    print(f"⚠️ API Status {e.code} caught. Cooldown for {delay}s... (Retry {attempt+1}/{retries})")
                    time.sleep(delay)
                    delay *= 2
                    continue
                print(f"❌ Catastrophic API JSON Error [{e.code}]: {e.message}")
                return {"error": f"API execution failed with code {e.code}", "message": e.message}
                
            except Exception as e:  # Catch JSON parsing formatting anomalies
                print(f"❌ JSON Parsing/System Exception: {e}")
                return {"error": "Could not parse structured response", "exception": str(e)}
