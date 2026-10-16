"""SET Compliance Rules Engine

Enforces Stock Exchange of Thailand (SET) trading rules:
1. 100-share Board Lots.
2. Official SET Tick Size Ladder.
3. Daily Ceiling/Floor Limits (±30%).
"""

import math
from typing import Tuple


class SETCompliance:
    BOARD_LOT_SIZE: int = 100
    CEILING_FLOOR_PERCENTAGE: float = 0.30

    @staticmethod
    def get_tick_size(price: float) -> float:
        """Return the official SET tick size based on price ladder.

        SET Price Ladder:
        - Less than 2.00 THB          -> 0.01 THB
        - 2.00 up to < 5.00 THB       -> 0.02 THB
        - 5.00 up to < 10.00 THB      -> 0.05 THB
        - 10.00 up to < 25.00 THB     -> 0.10 THB
        - 25.00 up to < 100.00 THB    -> 0.25 THB
        - 100.00 up to < 200.00 THB   -> 0.50 THB
        - 200.00 up to < 400.00 THB   -> 1.00 THB
        - 400.00 THB and above        -> 2.00 THB
        """
        if price <= 0:
            return 0.01
        if price < 2.00:
            return 0.01
        elif price < 5.00:
            return 0.02
        elif price < 10.00:
            return 0.05
        elif price < 25.00:
            return 0.10
        elif price < 100.00:
            return 0.25
        elif price < 200.00:
            return 0.50
        elif price < 400.00:
            return 1.00
        else:
            return 2.00

    @classmethod
    def round_to_valid_tick(cls, price: float, direction: str = "nearest") -> float:
        """Round price to valid SET tick size.

        direction: 'nearest', 'down', or 'up'
        """
        if price <= 0:
            return 0.01

        tick = cls.get_tick_size(price)
        units = price / tick

        if direction == "down":
            rounded_units = math.floor(units + 1e-9)
        elif direction == "up":
            rounded_units = math.ceil(units - 1e-9)
        else:
            rounded_units = round(units)

        result = rounded_units * tick
        # Clean precision floating point artifact
        return round(result, 2)

    @classmethod
    def calculate_ceiling_floor(cls, prev_close: float) -> Tuple[float, float]:
        """Calculate daily Ceiling and Floor (+30% / -30%) aligned to SET ticks."""
        if prev_close <= 0:
            return (0.01, 0.01)

        raw_ceiling = prev_close * (1.0 + cls.CEILING_FLOOR_PERCENTAGE)
        raw_floor = prev_close * (1.0 - cls.CEILING_FLOOR_PERCENTAGE)

        ceiling = cls.round_to_valid_tick(raw_ceiling, direction="down")
        floor = max(0.01, cls.round_to_valid_tick(raw_floor, direction="up"))

        return ceiling, floor

    @classmethod
    def round_board_lot(cls, shares: float) -> int:
        """Round shares down to nearest 100-share Board Lot.

        SET rules forbid odd-lot execution on the main board.
        """
        if shares < cls.BOARD_LOT_SIZE:
            return 0
        return int(shares // cls.BOARD_LOT_SIZE) * cls.BOARD_LOT_SIZE
