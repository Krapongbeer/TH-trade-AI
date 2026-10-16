"""SEC Open API Client (Securities and Exchange Commission of Thailand)

Handles:
1. Form 246-2: Acquisition or Disposition of Securities (Major Shareholders > 5%).
2. Form 59-2: Management & Director Securities Holding and Transaction Reports.
3. Cash Balance & Trading Alert List (Turnover List).
"""

from datetime import datetime, date
from typing import Dict, List, Optional
from pydantic import BaseModel


class Form59Transaction(BaseModel):
    symbol: str
    insider_name: str
    relationship: str
    transaction_date: date
    transaction_type: str  # "BUY", "SELL"
    shares: int
    price: float


class Form246Acquisition(BaseModel):
    symbol: str
    investor_name: str
    transaction_type: str  # "ACQUIRE", "DISPOSE"
    percent_before: float
    percent_after: float
    report_date: date


class CashBalanceRecord(BaseModel):
    symbol: str
    level: int  # 1: Cash Balance, 2: Prohibit Net Settlement, 3: Prohibit Net Settlement & Cash Balance
    effective_start: date
    effective_end: date
    reason: str


class SECOpenAPIClient:
    def __init__(self, api_key: str = "DEMO_KEY"):
        self.api_key = api_key
        # Cached lists
        self._cash_balance_list: Dict[str, CashBalanceRecord] = {}
        self._form59_reports: List[Form59Transaction] = []
        self._form246_reports: List[Form246Acquisition] = []

    def is_cash_balance(self, symbol: str) -> Optional[CashBalanceRecord]:
        """Check if symbol is currently penalized under SET Turnover / Cash Balance list."""
        return self._cash_balance_list.get(symbol.upper())

    def get_insider_transactions(self, symbol: str) -> List[Form59Transaction]:
        """Retrieve recent insider buying/selling transactions (Form 59-2)."""
        return [t for t in self._form59_reports if t.symbol.upper() == symbol.upper()]

    def get_major_shareholder_moves(self, symbol: str) -> List[Form246Acquisition]:
        """Retrieve Form 246-2 acquisition/disposition records."""
        return [a for a in self._form246_reports if a.symbol.upper() == symbol.upper()]

    def set_cash_balance_status(self, record: CashBalanceRecord) -> None:
        self._cash_balance_list[record.symbol.upper()] = record
