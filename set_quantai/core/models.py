"""Core Data Models (Pydantic v2) for SET-QuantAI

Strongly typed schema definitions for deterministic calculations,
LLM AI explainer validation, and persistence.
"""

from datetime import datetime, date
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class MarketDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


class SignalStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class OHLCVBar(BaseModel):
    timestamp: datetime
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    value: float = Field(default=0.0, ge=0)
    adjusted_close: Optional[float] = None


class FundamentalStatement(BaseModel):
    symbol: str
    period_date: date
    # Income statement
    revenue: float
    gross_profit: float
    operating_profit_ebit: float
    net_income: float
    # Balance sheet
    total_assets: float
    working_capital: float
    retained_earnings: float
    book_value_equity: float
    total_liabilities: float
    long_term_debt: float
    current_assets: float
    current_liabilities: float
    shares_outstanding: int
    # Cash flow
    cfo: float  # Operating Cash Flow


class PiotroskiScoreDetail(BaseModel):
    f_score: int = Field(..., ge=0, le=9)
    # Profitability (4 points)
    positive_roa: bool
    positive_cfo: bool
    higher_roa_yoy: bool
    accruals_quality: bool  # CFO > Net Income
    # Leverage/Liquidity (3 points)
    lower_debt_yoy: bool
    higher_current_ratio_yoy: bool
    no_share_dilution: bool
    # Efficiency (2 points)
    higher_gross_margin_yoy: bool
    higher_asset_turnover_yoy: bool
    passed: bool  # f_score >= 6
    summary_th: str


class AltmanZScoreDetail(BaseModel):
    z_double_prime: float
    x1_working_capital_to_assets: float
    x2_retained_earnings_to_assets: float
    x3_ebit_to_assets: float
    x4_equity_to_liabilities: float
    zone: str  # "SAFE", "GREY", "DISTRESS"
    is_disqualified: bool  # True if z_double_prime < 1.81
    summary_th: str


class ValuationDetail(BaseModel):
    pe_ratio: Optional[float] = None
    pbv_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    historical_5yr_pe_median: Optional[float] = None
    historical_5yr_pbv_median: Optional[float] = None
    sector_pe_percentile: Optional[float] = None
    valuation_status_th: str


class WyckoffStructure(BaseModel):
    trend: str  # "UPTREND", "DOWNTREND", "RANGING"
    higher_high: bool
    higher_low: bool
    choch_detected: bool  # Change of Character
    bos_detected: bool    # Break of Structure
    structure_summary_th: str


class VSASignal(BaseModel):
    stopping_volume: bool
    no_supply_bar: bool
    volume_ratio_20sma: float
    vsa_summary_th: str


class ConfluenceDetail(BaseModel):
    triple_ema_bullish: bool  # EMA 20 > 50 > 200
    ema20: float
    ema50: float
    ema200: float
    relative_strength_bullish: bool  # Stock vs SET trend
    rs_ratio: float
    vcp_contraction_detected: bool  # Volatility Contraction Pattern
    confluence_summary_th: str


class RiskAssessment(BaseModel):
    account_capital: float
    risk_percentage: float
    entry_price: float
    stop_loss_price: float
    target_price: float
    atr_14: float
    shares_allocated: int
    board_lots: int
    total_trade_value: float
    risk_amount_thb: float
    reward_risk_ratio: float
    is_rr_valid: bool  # R:R >= 2.0
    daily_drawdown_percent: float
    circuit_breaker_tripped: bool
    risk_summary_th: str


class AIExplainerOutput(BaseModel):
    symbol: str
    decision: MarketDirection
    confidence_score: float = Field(..., ge=0.0, le=100.0)
    headline_th: str
    fundamental_rationale_th: List[str]
    technical_rationale_th: List[str]
    risk_rationale_th: List[str]
    overall_recommendation_th: str


class TradeSignalRecord(BaseModel):
    signal_id: str
    generated_at: datetime
    symbol: str
    direction: MarketDirection
    strategy_name: str
    entry_price: float
    stop_loss: float
    target_1: float
    allocated_shares: int
    risk_reward_ratio: float
    rationale: Dict[str, Any]
    status: SignalStatus = SignalStatus.PENDING


class WatchlistItem(BaseModel):
    symbol: str
    notes: Optional[str] = None
    priority: int = 1
    target_price: Optional[float] = None
    alert_on_signal: bool = True
    added_at: datetime = Field(default_factory=datetime.now)
    tags: List[str] = Field(default_factory=list)


class WatchlistGroup(BaseModel):
    name: str
    description: Optional[str] = None
    items: List[WatchlistItem] = Field(default_factory=list)
