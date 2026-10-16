"""Altman Z''-Score Model (Emerging Market Formula)

Formula for Emerging Market Manufacturers & Non-Manufacturers:
Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4

Where:
- X1 = Working Capital / Total Assets
- X2 = Retained Earnings / Total Assets
- X3 = EBIT / Total Assets
- X4 = Book Value Equity / Total Liabilities

Zones of Discrimination:
- Z'' > 2.60: Safe Zone (สถานะการเงินมั่นคงมาก โอกาสล้มละลายต่ำ)
- 1.81 <= Z'' <= 2.60: Grey Zone (ระดับปานกลาง เฝ้าระวัง)
- Z'' < 1.81: Distress Zone (ความเสี่ยงล้มละลายสูง -> Disqualified ทันที)
"""

from set_quantai.core.models import FundamentalStatement, AltmanZScoreDetail


class AltmanZCalculator:
    DISQUALIFY_THRESHOLD: float = 1.81
    SAFE_THRESHOLD: float = 2.60

    @classmethod
    def calculate(cls, statement: FundamentalStatement) -> AltmanZScoreDetail:
        """Calculate Emerging Market Altman Z''-Score."""
        tot_assets = statement.total_assets if statement.total_assets > 0 else 1.0
        tot_liab = statement.total_liabilities if statement.total_liabilities > 0 else 1.0

        x1 = statement.working_capital / tot_assets
        x2 = statement.retained_earnings / tot_assets
        x3 = statement.operating_profit_ebit / tot_assets
        x4 = statement.book_value_equity / tot_liab

        z_score = (6.56 * x1) + (3.26 * x2) + (6.72 * x3) + (1.05 * x4)
        z_score = round(z_score, 3)

        if z_score >= cls.SAFE_THRESHOLD:
            zone = "SAFE"
            disqualified = False
            summary_th = f"Altman Z''-Score = {z_score:.2f} อยู่ใน Safe Zone (การเงินมั่นคงสูง ไม่มีความเสี่ยงผิดนัดชำระหนี้)"
        elif z_score >= cls.DISQUALIFY_THRESHOLD:
            zone = "GREY"
            disqualified = False
            summary_th = f"Altman Z''-Score = {z_score:.2f} อยู่ใน Grey Zone (ระดับเฝ้าระวัง ผ่านเกณฑ์ขั้นต่ำ {cls.DISQUALIFY_THRESHOLD})"
        else:
            zone = "DISTRESS"
            disqualified = True
            summary_th = f"Altman Z''-Score = {z_score:.2f} อยู่ใน Distress Zone (ต่ำกว่า 1.81 มีความเสี่ยงล้มละลาย ตัดสิทธิ์การเข้าเทรด)"

        return AltmanZScoreDetail(
            z_double_prime=z_score,
            x1_working_capital_to_assets=round(x1, 4),
            x2_retained_earnings_to_assets=round(x2, 4),
            x3_ebit_to_assets=round(x3, 4),
            x4_equity_to_liabilities=round(x4, 4),
            zone=zone,
            is_disqualified=disqualified,
            summary_th=summary_th,
        )
