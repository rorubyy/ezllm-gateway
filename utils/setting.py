import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MASTER_TOKEN: str = os.getenv("EZLLM_GATEWAY_MASTER_TOKEN", "sk-ezllm-master-token")
    PORT: int = int(os.getenv("PORT", 8080))

settings = Settings()
