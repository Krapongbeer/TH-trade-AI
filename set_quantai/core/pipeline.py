"""SET-QuantAI Unified Analysis Pipeline

Orchestrates all 5 system modules:
1. Data Engine (`data_engine`)
2. Deep Fundamental Screener (`fundamental_screener`)
3. Quantitative Technical Engine (`technical_analyser`)
4. Risk Management & Position Sizing (`risk_guard`)
5. Watchlist & Custom Universe Management (`watchlist_manager`)
With decoupled Pydantic AI Explainer reporting in Thai.
"""

from typing import Dict, List, Optional, Any
from set_quantai.config import Settings, load_settings
from set_quantai.core.models import (
    OHLCVBar,
    PiotroskiScoreDetail,
    AltmanZScoreDetail,
    ValuationDetail,
    WyckoffStructure,
    VSASignal,
    ConfluenceDetail,
    RiskAssessment,
    AIExplainerOutput,
    TradeSignalRecord,
    MarketDirection,
    SignalStatus,
)
from set_quantai.data_engine.settrade_client import SettradeClient
from set_quantai.data_engine.sec_client import SECOpenAPIClient
from set_quantai.data_engine.financial_statements import FinancialStatementsEngine
from set_quantai.fundamental_screener.piotroski import PiotroskiCalculator
from set_quantai.fundamental_screener.altman_z import AltmanZCalculator
from set_quantai.fundamental_screener.valuation import ValuationEngine
from set_quantai.technical_analyser.wyckoff_structure import WyckoffEngine
from set_quantai.technical_analyser.vsa import VSAEngine
from set_quantai.technical_analyser.confluence import ConfluenceEngine
from set_quantai.risk_guard.risk_manager import RiskGuard
from set_quantai.watchlist_manager.manager import WatchlistManager
from set_quantai.ai_explainer.explainer import AIExplainer
import uuid
from datetime import datetime


class AnalysisReport:
    def __init__(
        self,
        symbol: str,
        f_score: PiotroskiScoreDetail,
        altman: AltmanZScoreDetail,
        valuation: ValuationDetail,
        wyckoff: WyckoffStructure,
        vsa: VSASignal,
        confluence: ConfluenceDetail,
        risk: RiskAssessment,
        ai_explainer: AIExplainerOutput,
        trade_signal: Optional[TradeSignalRecord] = None,
    ):
        self.symbol = symbol
        self.f_score = f_score
        self.altman = altman
        self.valuation = valuation
        self.wyckoff = wyckoff
        self.vsa = vsa
        self.confluence = confluence
        self.risk = risk
        self.ai_explainer = ai_explainer
        self.trade_signal = trade_signal


class QuantAIPipeline:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or load_settings()
        self.settrade_client = SettradeClient(
            app_id=self.settings.settrade_app_id,
            app_secret=self.settings.settrade_app_secret,
            broker_id=self.settings.settrade_broker_id,
            app_code=self.settings.settrade_app_code,
            account_no=self.settings.settrade_account_no,
            pin=self.settings.settrade_pin,
        )
        self.sec_client = SECOpenAPIClient(api_key=self.settings.sec_api_key)
        self.financials_engine = FinancialStatementsEngine()
        self.risk_guard = RiskGuard(
            account_capital=self.settings.risk.default_capital,
            risk_per_trade_percent=self.settings.risk.max_risk_per_trade_percent,
            min_reward_risk_ratio=self.settings.risk.min_reward_risk_ratio,
            daily_drawdown_limit_percent=self.settings.risk.daily_drawdown_limit_percent,
        )
        self.watchlist_manager = WatchlistManager()

    def analyze_symbol(
        self,
        symbol: str,
        target_price: float = 0.0,
        timeframe: str = "D1",
    ) -> AnalysisReport:
        """Run end-to-end quantitative analysis for a given stock symbol."""
        symbol = symbol.strip().upper()

        # 1. Fetch Market Data & Financials
        bars = self.settrade_client.get_historical_bars(symbol, timeframe=timeframe, limit=120)
        statements = self.financials_engine.get_statements(symbol, limit=12)
        latest_statement = statements[-1] if statements else None
        current_price = bars[-1].close if bars else 50.0

        # Check target price from watchlist if not supplied
        if target_price <= 0:
            w_item = self.watchlist_manager.get_item(symbol)
            if w_item and w_item.target_price:
                target_price = w_item.target_price

        # 2. Fundamental Screener
        f_score_detail = PiotroskiCalculator.calculate(statements)
        altman_detail = AltmanZCalculator.calculate(latest_statement)
        valuation_detail = ValuationEngine.evaluate(symbol, current_price, latest_statement)

        # 3. Technical Analyser
        wyckoff_detail = WyckoffEngine.analyze_structure(bars)
        vsa_detail = VSAEngine.analyze(bars)
        confluence_detail = ConfluenceEngine.analyze(bars)

        # 4. Risk Guard & Position Sizing
        risk_detail = self.risk_guard.calculate_risk_parameters(
            entry_price=current_price,
            bars=bars,
            target_price=target_price,
        )

        # 5. AI Explainer
        ai_explainer_out = AIExplainer.generate_explanation(
            symbol=symbol,
            f_score_detail=f_score_detail,
            altman_detail=altman_detail,
            valuation_detail=valuation_detail,
            wyckoff_detail=wyckoff_detail,
            vsa_detail=vsa_detail,
            confluence_detail=confluence_detail,
            risk_detail=risk_detail,
        )

        # 6. Generate Trade Signal if Approved
        trade_signal = None
        if ai_explainer_out.decision == MarketDirection.BUY:
            trade_signal = TradeSignalRecord(
                signal_id=str(uuid.uuid4()),
                generated_at=datetime.now(),
                symbol=symbol,
                direction=MarketDirection.BUY,
                strategy_name="SET-QuantAI_Confluence_v1",
                entry_price=risk_detail.entry_price,
                stop_loss=risk_detail.stop_loss_price,
                target_1=risk_detail.target_price,
                allocated_shares=risk_detail.shares_allocated,
                risk_reward_ratio=risk_detail.reward_risk_ratio,
                rationale=ai_explainer_out.model_dump(),
                status=SignalStatus.PENDING,
            )

        return AnalysisReport(
            symbol=symbol,
            f_score=f_score_detail,
            altman=altman_detail,
            valuation=valuation_detail,
            wyckoff=wyckoff_detail,
            vsa=vsa_detail,
            confluence=confluence_detail,
            risk=risk_detail,
            ai_explainer=ai_explainer_out,
            trade_signal=trade_signal,
        )

    def scan_watchlist(self) -> List[AnalysisReport]:
        """Scan all stocks configured in user watchlist."""
        symbols = self.watchlist_manager.get_symbols()
        reports = []
        for sym in symbols:
            report = self.analyze_symbol(sym)
            reports.append(report)
        return reports
