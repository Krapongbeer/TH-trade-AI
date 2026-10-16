"""AI Explainer Engine (Decoupled LLM Reasoner & Validator)

Decoupled from deterministic quantitative calculations:
Takes audited quantitative inputs and generates structured, Pydantic-validated
Thai rationale reports and actionable trading recommendations.
"""

from typing import List
from set_quantai.core.models import (
    MarketDirection,
    PiotroskiScoreDetail,
    AltmanZScoreDetail,
    ValuationDetail,
    WyckoffStructure,
    VSASignal,
    ConfluenceDetail,
    RiskAssessment,
    AIExplainerOutput,
)


class AIExplainer:
    @staticmethod
    def generate_explanation(
        symbol: str,
        f_score_detail: PiotroskiScoreDetail,
        altman_detail: AltmanZScoreDetail,
        valuation_detail: ValuationDetail,
        wyckoff_detail: WyckoffStructure,
        vsa_detail: VSASignal,
        confluence_detail: ConfluenceDetail,
        risk_detail: RiskAssessment,
    ) -> AIExplainerOutput:
        """Synthesize deterministic quantitative results into structured Thai rationale."""
        symbol = symbol.upper()

        # Fundamental Rationales
        fund_points: List[str] = []
        if f_score_detail.passed:
            fund_points.append(f"✅ Piotroski F-Score แข็งแกร่งได้ {f_score_detail.f_score}/9 คะแนน (ผ่านเกณฑ์มาตรฐาน >= 6)")
        else:
            fund_points.append(f"⚠️ Piotroski F-Score ได้เพียง {f_score_detail.f_score}/9 คะแนน (ต่ำกว่าเกณฑ์ 6)")

        if f_score_detail.accruals_quality:
            fund_points.append("✅ คุณภาพกำไรโดดเด่น: กระแสเงินสดจากการดำเนินงาน (CFO) สูงกว่ากำไรสุทธิ")
        if f_score_detail.lower_debt_yoy:
            fund_points.append("✅ ภาระหนี้สินระยะยาวลดลงอย่างมีนัยสำคัญ")

        if altman_detail.is_disqualified:
            fund_points.append(f"❌ Altman Z''-Score ({altman_detail.z_double_prime:.2f}) ต่ำกว่า 1.81 อยู่ใน Distress Zone เสี่ยงล้มละลาย")
        else:
            fund_points.append(f"✅ Altman Z''-Score ({altman_detail.z_double_prime:.2f}) อยู่ในเกณฑ์ปลอดภัย ({altman_detail.zone} Zone)")

        fund_points.append(f"📊 มูลค่าพื้นฐาน: {valuation_detail.valuation_status_th}")

        # Technical Rationales
        tech_points: List[str] = []
        if wyckoff_detail.trend == "UPTREND":
            tech_points.append(f"✅ โครงสร้างแนวโน้ม Wyckoff ขาขึ้นชัดเจน (ทำ Higher-High และ Higher-Low)")
        elif wyckoff_detail.trend == "RANGING":
            tech_points.append("ℹ️ ราคาอยู่ในกรอบสะสมพลัง (Accumulation Zone)")
        else:
            tech_points.append("⚠️ โครงสร้างราคาเป็นขาลงหรือแรงขายยังคงกดดัน")

        if wyckoff_detail.choch_detected:
            tech_points.append("⚡ ตรวจพบสัญญาณ Change of Character (CHoCH) บ่งชี้การเปลี่ยนทิศทางแนวโน้ม")
        if wyckoff_detail.bos_detected:
            tech_points.append("🚀 ตรวจพบ Break of Structure (BOS) ทะลุแนวต้านเดิมยืนยันขาขึ้น")

        if vsa_detail.stopping_volume:
            tech_points.append(f"🔥 VSA Alert: พบ Stopping Volume แรงซื้อสถาบันดูดซับแรงขาย (วอลุ่ม {vsa_detail.volume_ratio_20sma:.1f}x)")
        elif vsa_detail.no_supply_bar:
            tech_points.append(f"🟢 VSA Alert: พบ No Supply Bar การย่อตัววอลุ่มแห้งขาดแรงขาย (วอลุ่มต่ำเพียง {vsa_detail.volume_ratio_20sma:.2f}x)")

        if confluence_detail.triple_ema_bullish:
            tech_points.append("✅ Triple EMA Alignment เรียงตัวสมบูรณ์แบบ (EMA 20 > EMA 50 > EMA 200)")
        if confluence_detail.relative_strength_bullish:
            tech_points.append("💪 หุ้นแสดง Relative Strength (RS Line) แข็งแกร่งกว่าดัชนีภาพรวมตลาด SET")
        if confluence_detail.vcp_contraction_detected:
            tech_points.append("🎯 Volatility Contraction Pattern (VCP): ความผันผวนบีบตัวพร้อมสำหรับการ Breakout")

        # Risk Rationales
        risk_points: List[str] = []
        if risk_detail.circuit_breaker_tripped:
            risk_points.append("🚨 พอร์ตแตะระดับ Circuit Breaker รายวัน (Drawdown >= 3.0%) ระบบสั่งระงับออเดอร์ทันที")
        else:
            risk_points.append(f"🛡️ ควบคุมความเสี่ยง {risk_detail.risk_percentage:.1f}% ของพอร์ต (มูลค่าความเสี่ยง {risk_detail.risk_amount_thb:,.2f} บาท)")

        risk_points.append(f"🎯 จุดตัดขาดทุน ATR: {risk_detail.stop_loss_price:.2f} THB | จุดทำกำไรเป้าหมาย: {risk_detail.target_price:.2f} THB")
        if risk_detail.is_rr_valid:
            risk_points.append(f"✅ Reward-to-Risk (R:R) เท่ากับ {risk_detail.reward_risk_ratio:.2f}:1 (ผ่านเกณฑ์ขั้นต่ำ 2.0:1)")
        else:
            risk_points.append(f"⚠️ Reward-to-Risk (R:R) ได้เพียง {risk_detail.reward_risk_ratio:.2f}:1 (ไม่ผ่านเกณฑ์ขั้นต่ำ 2.0:1)")

        risk_points.append(f"📦 ขนาดคำสั่งซื้อตามกฎ Board Lot (100 หุ้น): {risk_detail.shares_allocated:,} หุ้น ({risk_detail.board_lots:,} ล็อต)")

        # Decision Matrix (Deterministic Rule Evaluation)
        passed_fundamental = f_score_detail.passed and (not altman_detail.is_disqualified)
        bullish_technical = (
            (wyckoff_detail.trend == "UPTREND" or wyckoff_detail.choch_detected or wyckoff_detail.bos_detected)
            and (confluence_detail.triple_ema_bullish or confluence_detail.relative_strength_bullish or vsa_detail.stopping_volume)
        )
        passed_risk = risk_detail.is_rr_valid and (not risk_detail.circuit_breaker_tripped) and (risk_detail.shares_allocated >= 100)

        confidence = 0.0
        if altman_detail.is_disqualified or risk_detail.circuit_breaker_tripped:
            decision = MarketDirection.NEUTRAL
            confidence = 10.0
            headline = f"ระงับการเข้าซื้อหุ้น {symbol} เนื่องจากติดเงื่อนไขความเสี่ยงขั้นวิกฤต"
            recommendation = (
                f"หุ้น {symbol} ถูกตัดสิทธิ์ตามกฎความเสี่ยง "
                f"({'ความเสี่ยงล้มละลาย Altman Z < 1.81' if altman_detail.is_disqualified else 'พอร์ตแตะ Daily Drawdown Limit 3%'}) "
                "แนะนำให้รอจนกว่าสภาวะการเงินหรือพอร์ตจะกลับมาอยู่ในเกณฑ์ปลอดภัย"
            )
        elif passed_fundamental and bullish_technical and passed_risk:
            decision = MarketDirection.BUY
            # Calculate confidence based on confluence factors
            score_count = sum([
                f_score_detail.f_score >= 7,
                altman_detail.zone == "SAFE",
                wyckoff_detail.bos_detected or wyckoff_detail.choch_detected,
                confluence_detail.triple_ema_bullish,
                confluence_detail.relative_strength_bullish,
                vsa_detail.stopping_volume or vsa_detail.no_supply_bar,
                confluence_detail.vcp_contraction_detected,
                risk_detail.reward_risk_ratio >= 2.5,
            ])
            confidence = min(96.0, 70.0 + (score_count * 3.5))
            headline = f"อนุมัติสัญญาณซื้อ (BUY) สำหรับ {symbol}: ปัจจัยพื้นฐานและเทคนิคอลสอดคล้องสมบูรณ์"
            recommendation = (
                f"สัญญาณซื้อได้รับการยืนยันเต็มรูปแบบ! หุ้น {symbol} มีคะแนน F-Score สูงถึง {f_score_detail.f_score}/9, "
                f"โครงสร้างกราฟทำ {wyckoff_detail.trend} พร้อมทั้งมีสัญญาณยืนยันจาก VSA และ Triple EMA "
                f"กำหนดราคาเข้าซื้อที่ {risk_detail.entry_price:.2f} บาท, วาง Stop Loss ที่ {risk_detail.stop_loss_price:.2f} บาท "
                f"และเป้าหมายทำกำไร {risk_detail.target_price:.2f} บาท (R:R {risk_detail.reward_risk_ratio:.2f}:1) "
                f"ขนาดคำสั่งที่แนะนำคือ {risk_detail.shares_allocated:,} หุ้น"
            )
        else:
            decision = MarketDirection.NEUTRAL
            confidence = 45.0
            headline = f"คงสถานะเฝ้าดู (WATCH / NEUTRAL) สำหรับหุ้น {symbol}"
            recommendation = (
                f"หุ้น {symbol} มีเงื่อนไขบางประการที่ยังไม่ผ่านเกณฑ์ "
                f"({'พื้นฐานยังไม่ผ่าน F-Score < 6' if not passed_fundamental else ''} "
                f"{'โครงสร้างเทคนิคอลยังไม่ยืนยัน' if not bullish_technical else ''} "
                f"{'R:R ต่ำกว่า 2.0:1' if not risk_detail.is_rr_valid else ''}) "
                "แนะนำให้เพิ่มไว้ใน Watchlist เพื่อติดตามการฟอร์มตัวของโครงสร้างราคาต่อไป"
            )

        return AIExplainerOutput(
            symbol=symbol,
            decision=decision,
            confidence_score=round(confidence, 1),
            headline_th=headline,
            fundamental_rationale_th=fund_points,
            technical_rationale_th=tech_points,
            risk_rationale_th=risk_points,
            overall_recommendation_th=recommendation,
        )
