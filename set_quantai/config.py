"""Configuration Loader for SET-QuantAI

Reads settings from environment variables or config/settings.yaml
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from pydantic import BaseModel, Field


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "quant_password"
    dbname: str = "set_quantai"

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"


class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None


class RiskSettings(BaseModel):
    max_risk_per_trade_percent: float = 1.5  # 1.0% to 1.5%
    min_reward_risk_ratio: float = 2.0       # Minimum 2:1
    daily_drawdown_limit_percent: float = 3.0 # Halt if reached 3.0%
    atr_multiplier: float = 2.0              # Entry - (2.0 * ATR14)
    default_capital: float = 1_000_000.0     # Default 1,000,000 THB


class Settings(BaseModel):
    app_name: str = "SET-QuantAI"
    environment: str = "development"
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    settrade_app_id: str = "SANDBOX_APP_ID"
    settrade_app_secret: str = "SANDBOX_APP_SECRET"
    settrade_broker_id: str = "SANDBOX"
    settrade_app_code: str = "SANDBOX"
    settrade_account_no: str = "Kequiv-E"
    settrade_pin: str = "000000"
    sec_api_key: str = "DEMO_SEC_API_KEY"


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_settings() -> Settings:
    config_path = get_project_root() / "config" / "settings.yaml"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return Settings(**data)
        except Exception:
            return Settings()
    return Settings()
