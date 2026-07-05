import os
from dotenv import load_dotenv
load_dotenv()

IS_PRODUCTION = os.getenv("PROD_ENV", "false").lower() == "true"
MODEL_NAME = "gemini-2.5-pro" if IS_PRODUCTION else "gemini-3.5-flash"

if IS_PRODUCTION:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
    os.environ["GOOGLE_CLOUD_PROJECT"] = os.getenv("GCP_PROJECT_ID", "")
    os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv("GCP_LOCATION", "us-central1")
else:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")