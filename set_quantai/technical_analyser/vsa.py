"""Volume Spread Analysis (VSA) Engine

Detects:
1. Stopping Volume: Tight spread or long lower shadow with ultra-high volume (smart money absorbing sell orders).
2. No Supply Bar: Narrow-spread down bar on low volume below 20-day Volume SMA (lack of selling pressure).
"""

from typing import List
from set_quantai.core.models import OHLCVBar, VSASignal


class VSAEngine:
    @staticmethod
    def analyze(bars: List[OHLCVBar]) -> VSASignal:
        if len(bars) < 21:
            return VSASignal(
                stopping_volume=False,
                no_supply_bar=False,
                volume_ratio_20sma=1.0,
                vsa_summary_th="ข้อมูลไม่เพียงพอในการวิเคราะห์ Volume Spread Analysis (ต้องการอย่างน้อย 21 แท่ง)",
            )

        # Calculate 20-day volume SMA
        vol_sma20 = sum(b.volume for b in bars[-21:-1]) / 20.0
        latest = bars[-1]
        prev = bars[-2]

        vol_ratio = latest.volume / vol_sma20 if vol_sma20 > 0 else 1.0
        spread = latest.high - latest.low
        body = abs(latest.close - latest.open)
        lower_shadow = min(latest.open, latest.close) - latest.low

        avg_spread = sum(b.high - b.low for b in bars[-21:-1]) / 20.0
        is_tight_spread = spread <= avg_spread * 0.85
        has_long_lower_wick = lower_shadow >= (spread * 0.45) if spread > 0 else False

        # Stopping Volume condition:
        # Ultra-high volume (> 1.8x SMA20) AND (tight spread OR long lower shadow)
        is_stopping_vol = (vol_ratio >= 1.8) and (is_tight_spread or has_long_lower_wick)

        # No Supply Bar condition:
        # Down bar (close < prev close or close < open), narrow spread, volume strictly < SMA20 (e.g. < 0.75x)
        is_down_bar = latest.close <= prev.close
        is_no_supply = is_down_bar and is_tight_spread and (vol_ratio <= 0.75)

        summary_parts = []
        if is_stopping_vol:
            summary_parts.append(f"พบสัญญาณ Stopping Volume (วอลุ่มเข้ามหาศาล {vol_ratio:.1f}x ของ SMA20 พร้อมไส้ล่างยาว บ่งชี้แรงซื้อของสถาบันเข้าดูดซับแรงขาย)")
        elif is_no_supply:
            summary_parts.append(f"พบสัญญาณ No Supply Bar (การย่อตัวกรอบแคบและวอลุ่มแห้งต่ำกว่าปกติ {vol_ratio:.2f}x แสดงว่าแรงขายหมดสิ้น)")
        else:
            summary_parts.append(f"ปริมาณการซื้อขายปกติ ({vol_ratio:.1f}x ของ SMA20) ไม่พบพฤติกรรมผิดปกติของ Smart Money")

        return VSASignal(
            stopping_volume=is_stopping_vol,
            no_supply_bar=is_no_supply,
            volume_ratio_20sma=round(vol_ratio, 2),
            vsa_summary_th="; ".join(summary_parts),
        )
