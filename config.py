"""
Configuration management for LessonForge AI.
Handles environment variables, default settings, and directory initializations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent

# Load .env file if it exists
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class AppConfig:
    """Application configuration values with sensible defaults."""

    # Project metadata
    APP_NAME: str = "LessonForge AI"
    APP_VERSION: str = "1.0.0"
    TAGLINE: str = "From research to classroom-ready learning"

    # Directory Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    EXPORTS_DIR: Path = BASE_DIR / "exports"
    DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/lessons.db")

    # Hard Constraints
    MAX_LESSON_DURATION_MINUTES: int = int(os.getenv("MAX_LESSON_DURATION_MINUTES", "45"))
    MIN_LESSON_DURATION_MINUTES: int = 10
    DEFAULT_LESSON_DURATION_MINUTES: int = int(os.getenv("DEFAULT_LESSON_DURATION_MINUTES", "45"))

    # Provider Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()
    FALLBACK_MODE: str = os.getenv("FALLBACK_MODE", "auto").lower()

    # API Keys (Never hardcoded)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    def ensure_directories(self) -> None:
        """Ensure necessary runtime directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    def is_api_configured(self) -> bool:
        """Check if any valid LLM API key is present."""
        if self.FALLBACK_MODE == "force":
            return False
        if self.LLM_PROVIDER == "gemini" and self.GEMINI_API_KEY:
            return True
        if self.LLM_PROVIDER == "openai" and self.OPENAI_API_KEY:
            return True
        return False

    def get_effective_provider(self) -> str:
        """Return the active provider name, resolving to 'fallback' if keys are absent."""
        if self.FALLBACK_MODE == "force" or not self.is_api_configured():
            return "fallback"
        return self.LLM_PROVIDER


# Global singleton instance
config = AppConfig()
config.ensure_directories()
