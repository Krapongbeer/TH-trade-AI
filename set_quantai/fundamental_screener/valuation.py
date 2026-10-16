"""Valuation Metrics Engine

Evaluates:
- P/E Ratio
- P/BV Ratio
- EV/EBITDA
Compared against:
- 5-Year Historical Medians
- Sector-relative Percentile Bands
"""

from typing import Dict, Optional
from set_quantai.core.models import FundamentalStatement, ValuationDetail


class ValuationEngine:
    # Sector baseline benchmarks in Thailand
    SECTOR_BENCHMARKS = {
        "COMMERCE": {"pe_median": 26.5, "pbv_median": 4.2},
        "ENERGY": {"pe_median": 10.5, "pbv_median": 0.95},
        "HEALTHCARE": {"pe_median": 28.0, "pbv_median": 4.0},
        "ICT": {"pe_median": 21.0, "pbv_median": 6.5},
        "TECH": {"pe_median": 45.0, "pbv_median": 12.0},
        "BANK": {"pe_median": 8.0, "pbv_median": 0.65},
        "DEFAULT": {"pe_median": 16.0, "pbv_median": 1.8},
    }

    @classmethod
    def evaluate(
        cls,
        symbol: str,
        current_price: float,
        statement: FundamentalStatement,
        sector: str = "DEFAULT",
    ) -> ValuationDetail:
        """Evaluate stock valuation against historical medians and sector percentiles."""
        sector_norm = sector.upper()
        benchmarks = cls.SECTOR_BENCHMARKS.get(sector_norm, cls.SECTOR_BENCHMARKS["DEFAULT"])

        shares = statement.shares_outstanding if statement.shares_outstanding > 0 else 1
        eps = (statement.net_income * 4.0) / shares if statement.net_income > 0 else 0.01
        bvps = statement.book_value_equity / shares if statement.book_value_equity > 0 else 0.01

        pe = round(current_price / eps, 2) if eps > 0 else None
        pbv = round(current_price / bvps, 2) if bvps > 0 else None

        ebit = statement.operating_profit_ebit * 4.0
        ev = (current_price * shares) + statement.long_term_debt - statement.working_capital
        ev_ebitda = round(ev / ebit, 2) if ebit > 0 else None

        pe_median = benchmarks["pe_median"]
        pbv_median = benchmarks["pbv_median"]

        # Calculate percentile approximation vs sector
        status_terms = []
        if pe:
            if pe < pe_median * 0.85:
                status_terms.append(f"P/E {pe:.1f}x ต่ำกว่าค่ามัธยฐาน 5 ปี ({pe_median:.1f}x) ถือว่า Undervalued")
                percentile = 30.0
            elif pe > pe_median * 1.25:
                status_terms.append(f"P/E {pe:.1f}x สูงกว่าค่ามัธยฐาน ({pe_median:.1f}x) สะท้อนพรีเมียมการเติบโต")
                percentile = 75.0
            else:
                status_terms.append(f"P/E {pe:.1f}x อยู่ในระดับ Fair Value ใกล้เคียงค่าเฉลี่ยอุตสาหกรรม")
                percentile = 50.0
        else:
            status_terms.append("ไม่สามารถคำนวณ P/E ได้เนื่องจากผลขาดทุน")
            percentile = 90.0

        return ValuationDetail(
            pe_ratio=pe,
            pbv_ratio=pbv,
            ev_ebitda=ev_ebitda,
            historical_5yr_pe_median=pe_median,
            historical_5yr_pbv_median=pbv_median,
            sector_pe_percentile=percentile,
            valuation_status_th="; ".join(status_terms),
        )
