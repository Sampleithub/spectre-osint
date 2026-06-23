import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.7"))
    max_rounds: int = int(os.getenv("MAX_INVESTIGATION_ROUNDS", "25"))
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    data_dir: str = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))


config = Config()
