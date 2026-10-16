"""Piotroski F-Score Calculation Engine (Audited 9-Criteria Model)

Scores fundamental strength from 0 to 9:
- Profitability (4 points)
- Leverage, Liquidity and Source of Funds (3 points)
- Operating Efficiency (2 points)

Passing Rule: F-Score >= 6
"""

from typing import List, Optional
from set_quantai.core.models import FundamentalStatement, PiotroskiScoreDetail


class PiotroskiCalculator:
    @staticmethod
    def calculate(statements: List[FundamentalStatement]) -> PiotroskiScoreDetail:
        """Calculate Piotroski F-Score using the latest statement compared with prior year."""
        if len(statements) < 2:
            # Insufficient statements fallback
            return PiotroskiScoreDetail(
                f_score=0,
                positive_roa=False,
                positive_cfo=False,
                higher_roa_yoy=False,
                accruals_quality=False,
                lower_debt_yoy=False,
                higher_current_ratio_yoy=False,
                no_share_dilution=False,
                higher_gross_margin_yoy=False,
                higher_asset_turnover_yoy=False,
                passed=False,
                summary_th="ข้อมูลรายงานงบการเงินไม่เพียงพอสำหรับการประเมิน Piotroski F-Score (ต้องใช้งบอย่างน้อย 2 ไตรมาส)",
            )

        curr = statements[-1]
        prev = statements[-5] if len(statements) >= 5 else statements[-2]  # YoY preferred

        # 1. Profitability (4 criteria)
        # 1.1 ROA > 0
        roa_curr = curr.net_income / curr.total_assets if curr.total_assets > 0 else 0
        roa_prev = prev.net_income / prev.total_assets if prev.total_assets > 0 else 0
        p_roa = roa_curr > 0

        # 1.2 CFO > 0
        p_cfo = curr.cfo > 0

        # 1.3 ΔROA > 0
        p_delta_roa = roa_curr > roa_prev

        # 1.4 Accruals: CFO > Net Income (Quality of earnings)
        p_accruals = curr.cfo > curr.net_income

        # 2. Leverage / Liquidity / Dilution (3 criteria)
        # 2.1 ΔLong-term Debt <= 0
        p_lower_debt = curr.long_term_debt <= prev.long_term_debt

        # 2.2 ΔCurrent Ratio > 0
        cr_curr = curr.current_assets / curr.current_liabilities if curr.current_liabilities > 0 else 0
        cr_prev = prev.current_assets / prev.current_liabilities if prev.current_liabilities > 0 else 0
        p_delta_cr = cr_curr > cr_prev

        # 2.3 No share dilution (shares_outstanding <= prev)
        p_no_dilution = curr.shares_outstanding <= prev.shares_outstanding

        # 3. Operating Efficiency (2 criteria)
        # 3.1 ΔGross Margin > 0
        gm_curr = curr.gross_profit / curr.revenue if curr.revenue > 0 else 0
        gm_prev = prev.gross_profit / prev.revenue if prev.revenue > 0 else 0
        p_delta_gm = gm_curr > gm_prev

        # 3.2 ΔAsset Turnover > 0
        at_curr = curr.revenue / curr.total_assets if curr.total_assets > 0 else 0
        at_prev = prev.revenue / prev.total_assets if prev.total_assets > 0 else 0
        p_delta_at = at_curr > at_prev

        # Compute total score
        points = [
            p_roa, p_cfo, p_delta_roa, p_accruals,
            p_lower_debt, p_delta_cr, p_no_dilution,
            p_delta_gm, p_delta_at,
        ]
        score = sum(1 for p in points if p)
        passed = score >= 6

        # Thai summary
        summary_parts = []
        if passed:
            summary_parts.append(f"คะแนน F-Score อยู่ในเกณฑ์แข็งแกร่งมาก ({score}/9 ผ่านเกณฑ์ขั้นต่ำ 6)")
        else:
            summary_parts.append(f"คะแนน F-Score ยังไม่ผ่านเกณฑ์ ({score}/9 ต่ำกว่าเกณฑ์มาตรฐาน 6)")

        if p_accruals:
            summary_parts.append("คุณภาพกำไรสูง (กระแสเงินสด CFO สูงกว่ากำไรสุทธิ)")
        if p_lower_debt:
            summary_parts.append("หนี้สินระยะยาวลดลงหรือคงที่")
        if not p_no_dilution:
            summary_parts.append("มีการเพิ่มทุนหรือออกหุ้นใหม่ (Dilution)")

        return PiotroskiScoreDetail(
            f_score=score,
            positive_roa=p_roa,
            positive_cfo=p_cfo,
            higher_roa_yoy=p_delta_roa,
            accruals_quality=p_accruals,
            lower_debt_yoy=p_lower_debt,
            higher_current_ratio_yoy=p_delta_cr,
            no_share_dilution=p_no_dilution,
            higher_gross_margin_yoy=p_delta_gm,
            higher_asset_turnover_yoy=p_delta_at,
            passed=passed,
            summary_th="; ".join(summary_parts),
        )
