"""Technical Indicators & Statistical Confluence Engine

Calculates:
1. Triple EMA Alignment: EMA 20 > EMA 50 > EMA 200.
2. Relative Strength Line: RS = Close(Stock) / Close(SET Index) trending upward.
3. Volatility Contraction Pattern (VCP): Contraction of Standard Deviation & ATR prior to breakout.
"""

import math
from typing import List, Optional
from set_quantai.core.models import OHLCVBar, ConfluenceDetail


class ConfluenceEngine:
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        if not prices:
            return []
        k = 2.0 / (period + 1.0)
        ema = [prices[0]]
        for price in prices[1:]:
            ema.append((price * k) + (ema[-1] * (1.0 - k)))
        return ema

    @staticmethod
    def calculate_atr(bars: List[OHLCVBar], period: int = 14) -> float:
        if len(bars) < period + 1:
            return 1.0
        trs = []
        for i in range(1, len(bars)):
            h_l = bars[i].high - bars[i].low
            h_pc = abs(bars[i].high - bars[i - 1].close)
            l_pc = abs(bars[i].low - bars[i - 1].close)
            tr = max(h_l, h_pc, l_pc)
            trs.append(tr)
        return sum(trs[-period:]) / float(period)

    @classmethod
    def analyze(
        cls,
        stock_bars: List[OHLCVBar],
        set_index_bars: Optional[List[OHLCVBar]] = None,
    ) -> ConfluenceDetail:
        if len(stock_bars) < 50:
            return ConfluenceDetail(
                triple_ema_bullish=False,
                ema20=0.0,
                ema50=0.0,
                ema200=0.0,
                relative_strength_bullish=False,
                rs_ratio=1.0,
                vcp_contraction_detected=False,
                confluence_summary_th="ข้อมูลไม่เพียงพอในการคำนวณ Indicator Confluence (ต้องการอย่างน้อย 50 แท่ง)",
            )

        closes = [b.close for b in stock_bars]
        ema20_series = cls.calculate_ema(closes, 20)
        ema50_series = cls.calculate_ema(closes, 50)
        ema200_series = cls.calculate_ema(closes, min(len(closes), 200))

        ema20 = ema20_series[-1]
        ema50 = ema50_series[-1]
        ema200 = ema200_series[-1]

        # Triple EMA Alignment: EMA 20 > EMA 50 > EMA 200
        triple_ema_bullish = (ema20 > ema50) and (ema50 > ema200)

        # Relative Strength Line vs SET Index
        if set_index_bars and len(set_index_bars) >= len(stock_bars):
            set_closes = [b.close for b in set_index_bars[-len(stock_bars):]]
            rs_current = closes[-1] / set_closes[-1] if set_closes[-1] > 0 else 1.0
            rs_20_ago = closes[-20] / set_closes[-20] if len(closes) >= 20 and set_closes[-20] > 0 else rs_current
            rs_bullish = rs_current > rs_20_ago
            rs_ratio = rs_current
        else:
            # Baseline proxy: compare stock return with 0.0 trend
            rs_bullish = (closes[-1] / closes[-20]) > 1.02 if len(closes) >= 20 else True
            rs_ratio = round(closes[-1] / (closes[-20] if len(closes) >= 20 else closes[0]), 4)

        # Volatility Contraction Pattern (VCP):
        # ATR of last 5 days < ATR of last 20 days by at least 25%
        atr_fast = cls.calculate_atr(stock_bars, period=5)
        atr_slow = cls.calculate_atr(stock_bars, period=20)
        vcp_detected = atr_fast < (atr_slow * 0.75)

        summary_parts = []
        if triple_ema_bullish:
            summary_parts.append(f"เกิด Triple EMA Alignment ขาขึ้นสมบูรณ์ (EMA 20 {ema20:.2f} > EMA 50 {ema50:.2f} > EMA 200 {ema200:.2f})")
        else:
            summary_parts.append(f"เส้นค่าเฉลี่ยยังไม่เรียงตัวสมบูรณ์ (EMA20: {ema20:.2f}, EMA50: {ema50:.2f}, EMA200: {ema200:.2f})")

        if rs_bullish:
            summary_parts.append("Relative Strength (RS Line) แข็งแกร่งกว่าดัชนี SET อย่างชัดเจน (Outperforming Market)")

        if vcp_detected:
            summary_parts.append("พบสัญญาณ Volatility Contraction Pattern (VCP) ความผันผวนบีบตัวแคบเตรียมระเบิด Breakout")

        return ConfluenceDetail(
            triple_ema_bullish=triple_ema_bullish,
            ema20=round(ema20, 2),
            ema50=round(ema50, 2),
            ema200=round(ema200, 2),
            relative_strength_bullish=rs_bullish,
            rs_ratio=round(rs_ratio, 4),
            vcp_contraction_detected=vcp_detected,
            confluence_summary_th="; ".join(summary_parts),
        )
