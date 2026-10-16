"""Wyckoff Market Structure Engine

Detects:
1. Fractal Pivots (Swing Highs and Swing Lows).
2. Trend Identification: Higher-High / Higher-Low (Uptrend) vs Lower-High / Lower-Low (Downtrend).
3. Change of Character (CHoCH) - Early reversal signal.
4. Break of Structure (BOS) - Trend continuation confirmation.
"""

from typing import List, Tuple
from set_quantai.core.models import OHLCVBar, WyckoffStructure


class WyckoffEngine:
    @staticmethod
    def find_fractal_pivots(bars: List[OHLCVBar], window: int = 2) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """Detect swing highs and swing lows using fractal pivot algorithm (2 bars left and right)."""
        swing_highs = []
        swing_lows = []
        n = len(bars)

        for i in range(window, n - window):
            curr_high = bars[i].high
            curr_low = bars[i].low

            # Check swing high
            if all(curr_high > bars[i - j].high for j in range(1, window + 1)) and \
               all(curr_high >= bars[i + j].high for j in range(1, window + 1)):
                swing_highs.append((i, curr_high))

            # Check swing low
            if all(curr_low < bars[i - j].low for j in range(1, window + 1)) and \
               all(curr_low <= bars[i + j].low for j in range(1, window + 1)):
                swing_lows.append((i, curr_low))

        return swing_highs, swing_lows

    @classmethod
    def analyze_structure(cls, bars: List[OHLCVBar]) -> WyckoffStructure:
        if len(bars) < 20:
            return WyckoffStructure(
                trend="RANGING",
                higher_high=False,
                higher_low=False,
                choch_detected=False,
                bos_detected=False,
                structure_summary_th="ข้อมูลราคาไม่เพียงพอในการวิเคราะห์โครงสร้างตลาด Wyckoff",
            )

        swing_highs, swing_lows = cls.find_fractal_pivots(bars)
        latest_close = bars[-1].close

        hh = False
        hl = False
        choch = False
        bos = False

        if len(swing_highs) >= 2:
            hh = swing_highs[-1][1] > swing_highs[-2][1]
        if len(swing_lows) >= 2:
            hl = swing_lows[-1][1] > swing_lows[-2][1]

        # Break of Structure (BOS): Latest close cleanly breaches prior swing high in uptrend
        if swing_highs and latest_close > swing_highs[-1][1]:
            bos = True

        # Change of Character (CHoCH): Trend transitions from downtrend (LH/LL) to higher high
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            prior_downtrend = swing_highs[-2][1] < (swing_highs[-3][1] if len(swing_highs) >= 3 else swing_highs[-2][1])
            if prior_downtrend and latest_close > swing_highs[-1][1]:
                choch = True

        # Determine overall trend
        if hh and hl:
            trend = "UPTREND"
            summary_th = "โครงสร้างราคาขาขึ้นสมบูรณ์ (Higher-High & Higher-Low ตามทฤษฎี Wyckoff)"
        elif not hh and not hl:
            trend = "DOWNTREND"
            summary_th = "โครงสร้างราคาขาลง (Lower-High & Lower-Low)"
        else:
            trend = "RANGING"
            summary_th = "โครงสร้างราคากำลังสะสมในกรอบ (Accumulation / Re-accumulation Range)"

        if choch:
            summary_th += " | เกิดสัญญาณเปลี่ยนพฤติกรรมราคา CHoCH (Change of Character) บ่งชี้จุดกลับตัวขาขึ้น"
        elif bos:
            summary_th += " | เกิดสัญญาณ Break of Structure (BOS) ยืนยันการไปต่อของแนวโน้มขาขึ้น"

        return WyckoffStructure(
            trend=trend,
            higher_high=hh,
            higher_low=hl,
            choch_detected=choch,
            bos_detected=bos,
            structure_summary_th=summary_th,
        )
