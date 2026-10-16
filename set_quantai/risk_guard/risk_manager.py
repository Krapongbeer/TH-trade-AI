"""Risk Management & Position Sizing Engine (`risk_guard`)

Implements:
1. Position Sizing Formula:
   Position Size (Shares) = (Account Capital * Risk %) / (Entry Price - Stop Loss Price)
   - Max Risk: 1.0% to 1.5% of total portfolio equity.
   - Enforces 100-share Board Lot round-down rule.
2. Dynamic Volatility Stop Loss:
   Initial Stop = Entry - (2.0 * ATR14), aligned to SET Tick Size ladder.
3. Execution Gate:
   Reward-to-Risk (R:R) ratio must be >= 2.0:1.
4. Circuit Breakers:
   Daily portfolio drawdown threshold at 3.0%. If breached, halt order generation immediately.
"""

from typing import Tuple
from set_quantai.core.compliance import SETCompliance
from set_quantai.core.models import RiskAssessment, OHLCVBar
from set_quantai.technical_analyser.confluence import ConfluenceEngine


class RiskGuard:
    def __init__(
        self,
        account_capital: float = 1_000_000.0,
        risk_per_trade_percent: float = 1.5,
        min_reward_risk_ratio: float = 2.0,
        daily_drawdown_limit_percent: float = 3.0,
    ):
        self.account_capital = account_capital
        self.risk_per_trade_percent = min(max(risk_per_trade_percent, 1.0), 1.5)  # Constrained to 1.0% - 1.5%
        self.min_reward_risk_ratio = min_reward_risk_ratio
        self.daily_drawdown_limit_percent = daily_drawdown_limit_percent
        self.current_daily_drawdown_percent = 0.0

    def calculate_atr_stop_loss(self, entry_price: float, bars: list) -> Tuple[float, float]:
        """Calculate dynamic volatility stop loss = Entry - (2.0 * ATR14)."""
        atr14 = ConfluenceEngine.calculate_atr(bars, period=14)
        raw_stop = entry_price - (2.0 * atr14)
        # Stop loss rounded to valid SET tick size (downward to be conservative)
        stop_loss = SETCompliance.round_to_valid_tick(max(0.01, raw_stop), direction="down")
        return stop_loss, round(atr14, 2)

    def calculate_risk_parameters(
        self,
        entry_price: float,
        bars: list,
        target_price: float = 0.0,
    ) -> RiskAssessment:
        """Compute strict quantitative position sizing and risk validation."""
        # 1. Circuit breaker check
        is_circuit_breaker_tripped = self.current_daily_drawdown_percent >= self.daily_drawdown_limit_percent

        # 2. Dynamic ATR Stop Loss
        stop_loss, atr14 = self.calculate_atr_stop_loss(entry_price, bars)
        per_share_risk = entry_price - stop_loss

        if per_share_risk <= 0:
            per_share_risk = SETCompliance.get_tick_size(entry_price) * 2

        # 3. Target calculation (if not specified, default to R:R = 2.5:1)
        if target_price <= entry_price:
            raw_target = entry_price + (per_share_risk * 2.5)
            target_price = SETCompliance.round_to_valid_tick(raw_target, direction="up")

        # 4. Reward-to-Risk (R:R) Ratio
        per_share_reward = target_price - entry_price
        rr_ratio = round(per_share_reward / per_share_risk, 2) if per_share_risk > 0 else 0.0
        is_rr_valid = rr_ratio >= self.min_reward_risk_ratio

        # 5. Position Sizing
        risk_budget_thb = self.account_capital * (self.risk_per_trade_percent / 100.0)
        raw_shares = risk_budget_thb / per_share_risk
        allocated_shares = SETCompliance.round_board_lot(raw_shares)
        board_lots = allocated_shares // SETCompliance.BOARD_LOT_SIZE
        trade_value = round(allocated_shares * entry_price, 2)
        actual_risk_thb = round(allocated_shares * per_share_risk, 2)

        # Thai summary
        summary_parts = []
        if is_circuit_breaker_tripped:
            summary_parts.append(f"🚨 CIRCUIT BREAKER TRIP: ขาดทุนสะสมรายวัน {self.current_daily_drawdown_percent:.2f}% เกินเกณฑ์ 3.0% ระงับการสั่งซื้อขายทันที!")
        else:
            summary_parts.append(f"ระบบบริหารความเสี่ยงอนุมัติ: ความเสี่ยงต่อไม้ {self.risk_per_trade_percent:.1f}% ({risk_budget_thb:,.2f} บาท)")

        summary_parts.append(f"จุดเข้าซื้อ: {entry_price:.2f} บาท | จุดตัดขาดทุน ATR: {stop_loss:.2f} บาท | เป้าหมายกำไร: {target_price:.2f} บาท")
        summary_parts.append(f"Reward-to-Risk (R:R) = {rr_ratio:.2f}:1 ({'ผ่านเกณฑ์ >= 2.0' if is_rr_valid else 'ไม่ผ่านเกณฑ์ขั้นต่ำ 2.0:1'})")
        summary_parts.append(f"ขนาดไม้ที่คำนวณได้: {allocated_shares:,} หุ้น ({board_lots:,} Board Lots) มูลค่าเงินลงทุน {trade_value:,.2f} บาท")

        return RiskAssessment(
            account_capital=self.account_capital,
            risk_percentage=self.risk_per_trade_percent,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            target_price=target_price,
            atr_14=atr14,
            shares_allocated=allocated_shares,
            board_lots=board_lots,
            total_trade_value=trade_value,
            risk_amount_thb=actual_risk_thb,
            reward_risk_ratio=rr_ratio,
            is_rr_valid=is_rr_valid,
            daily_drawdown_percent=self.current_daily_drawdown_percent,
            circuit_breaker_tripped=is_circuit_breaker_tripped,
            risk_summary_th=" | ".join(summary_parts),
        )
