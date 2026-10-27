"""Settings read from the environment (.env at the repo root)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    model_api_key: str | None
    model_base_url: str
    baseten_api_key: str | None
    baseten_base_url: str
    baseten_model: str
    cost_log: Path
    fb_token: str | None = None
    fb_api_version: str = "v26.0"


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    return Settings(
        model_api_key=os.getenv("MODEL_API_KEY") or None,
        model_base_url=os.getenv("META_MODEL_BASE_URL", "https://api.meta.ai/v1"),
        baseten_api_key=os.getenv("BASETEN_API_KEY") or None,
        baseten_base_url=os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1"),
        baseten_model=os.getenv("BASETEN_MODEL", "meta-models/muse-spark-open"),
        cost_log=Path(os.getenv("WHYNOT_COST_LOG") or REPO_ROOT / "outputs" / "costs.jsonl"),
        fb_token=os.getenv("FB_TOKEN") or None,
        fb_api_version=os.getenv("FB_API_VERSION", "v26.0"),
    )
