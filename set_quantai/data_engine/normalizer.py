"""Data Normalization Engine

Handles:
1. Multi-timeframe resampling: M15, H1, H4, D1, W1.
2. Historical price adjustment for Corporate Actions (XD, XR, XW, Splits).
"""

from datetime import datetime, timedelta
from typing import List, Optional
from set_quantai.core.models import OHLCVBar


class CorporateAction:
    def __init__(self, ex_date: datetime, action_type: str, ratio: float, dividend: float = 0.0):
        self.ex_date = ex_date
        self.action_type = action_type  # "SPLIT", "XD", "XR", "XW"
        self.ratio = ratio
        self.dividend = dividend


class DataNormalizer:
    @staticmethod
    def adjust_for_corporate_actions(bars: List[OHLCVBar], actions: List[CorporateAction]) -> List[OHLCVBar]:
        """Adjust historical prices backward from corporate actions so indicators remain continuous."""
        if not bars:
            return []

        adjusted_bars = [bar.model_copy() for bar in bars]
        # Sort bars chronologically
        adjusted_bars.sort(key=lambda b: b.timestamp)

        # For each action, adjust prices before ex_date
        for act in sorted(actions, key=lambda a: a.ex_date, reverse=True):
            factor = 1.0
            if act.action_type == "SPLIT" and act.ratio > 0:
                factor = 1.0 / act.ratio
            elif act.action_type == "XD" and act.dividend > 0:
                # Find price at ex-date
                target_bar = next((b for b in adjusted_bars if b.timestamp >= act.ex_date), None)
                if target_bar and target_bar.close > act.dividend:
                    factor = (target_bar.close - act.dividend) / target_bar.close

            for bar in adjusted_bars:
                if bar.timestamp < act.ex_date:
                    bar.open = round(bar.open * factor, 2)
                    bar.high = round(bar.high * factor, 2)
                    bar.low = round(bar.low * factor, 2)
                    bar.close = round(bar.close * factor, 2)
                    bar.adjusted_close = bar.close
                else:
                    bar.adjusted_close = bar.close

        return adjusted_bars

    @staticmethod
    def resample_timeframe(bars: List[OHLCVBar], target_timeframe: str) -> List[OHLCVBar]:
        """Resample 1-minute or base bars into M15, H1, H4, D1, W1."""
        if not bars:
            return []

        tf_minutes = {
            "M15": 15,
            "H1": 60,
            "H4": 240,
            "D1": 1440,
            "W1": 10080,
        }

        mins = tf_minutes.get(target_timeframe.upper(), 60)
        sorted_bars = sorted(bars, key=lambda b: b.timestamp)

        resampled: List[OHLCVBar] = []
        current_bucket: List[OHLCVBar] = []
        bucket_start: Optional[datetime] = None

        def get_bucket_boundary(dt: datetime, interval_m: int) -> datetime:
            minute_floor = (dt.minute // interval_m) * interval_m if interval_m < 60 else 0
            hour_floor = (dt.hour // (interval_m // 60)) * (interval_m // 60) if interval_m >= 60 else dt.hour
            return dt.replace(hour=hour_floor, minute=minute_floor, second=0, microsecond=0)

        for bar in sorted_bars:
            b_time = get_bucket_boundary(bar.timestamp, mins if mins < 60 else 60)
            if bucket_start is None:
                bucket_start = b_time

            if (bar.timestamp - bucket_start) < timedelta(minutes=mins):
                current_bucket.append(bar)
            else:
                if current_bucket:
                    resampled.append(
                        OHLCVBar(
                            timestamp=bucket_start,
                            open=current_bucket[0].open,
                            high=max(b.high for b in current_bucket),
                            low=min(b.low for b in current_bucket),
                            close=current_bucket[-1].close,
                            volume=sum(b.volume for b in current_bucket),
                            value=sum(b.value for b in current_bucket),
                            adjusted_close=current_bucket[-1].adjusted_close or current_bucket[-1].close,
                        )
                    )
                bucket_start = b_time
                current_bucket = [bar]

        if current_bucket and bucket_start:
            resampled.append(
                OHLCVBar(
                    timestamp=bucket_start,
                    open=current_bucket[0].open,
                    high=max(b.high for b in current_bucket),
                    low=min(b.low for b in current_bucket),
                    close=current_bucket[-1].close,
                    volume=sum(b.volume for b in current_bucket),
                    value=sum(b.value for b in current_bucket),
                    adjusted_close=current_bucket[-1].adjusted_close or current_bucket[-1].close,
                )
            )

        return resampled
