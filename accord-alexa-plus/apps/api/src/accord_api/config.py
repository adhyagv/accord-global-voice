"""Runtime configuration for Accord API."""

from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    api_title: str = "Accord API"
    api_version: str = "0.3.0"
    api_prefix: str = "/api"


settings = Settings()
