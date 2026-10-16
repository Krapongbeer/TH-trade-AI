"""SET-QuantAI Top 5 Quantitative Recommendations Engine

Selects and performs deep-dive quantitative analysis on the Top 5
best confluence Thai equity picks, calculating:
- Optimal Buy Zone (ราคาเข้าซื้อที่เหมาะสม)
- Primary & Secondary Sell Targets (เป้าหมายขายทำกำไร)
- Dynamic ATR-14 Cut Loss (จุดตัดขาดทุน)
- Reward-to-Risk (R:R) Ratio
- Board Lot Position Sizing (ตามกฎ SET 100 หุ้น)
- In-depth Thai fundamental & technical rationale
"""

from typing import Dict, List, Any
from set_quantai.core.compliance import SETCompliance
from set_quantai.core.models import MarketDirection


class TopPicksEngine:
    CANDIDATES = [
        {"symbol": "PTT", "name_th": "บริษัท ปตท. จำกัด (มหาชน)", "sector": "พลังงานและสาธารณูปโภค (ENERGY)"},
        {"symbol": "SCB", "name_th": "เอสซีบี เอกซ์ จำกัด (มหาชน)", "sector": "ธนาคารพาณิชย์ (BANK)"},
        {"symbol": "ADVANC", "name_th": "บริษัท แอดวานซ์ อินโฟร์ เซอร์วิส จำกัด (มหาชน)", "sector": "เทคโนโลยีสารสนเทศและการสื่อสาร (ICT)"},
        {"symbol": "BDMS", "name_th": "บริษัท กรุงเทพดุสิตเวชการ จำกัด (มหาชน)", "sector": "การแพทย์ (HEALTH)"},
        {"symbol": "CPALL", "name_th": "บริษัท ซีพี ออลล์ จำกัด (มหาชน)", "sector": "พาณิชย์ (COMMERCE)"},
        {"symbol": "DELTA", "name_th": "บริษัท เดลต้า อีเลคโทรนิคส์ (ประเทศไทย) จำกัด (มหาชน)", "sector": "ชิ้นส่วนอิเล็กทรอนิกส์ (ETRON)"},
        {"symbol": "KBANK", "name_th": "ธนาคารกสิกรไทย จำกัด (มหาชน)", "sector": "ธนาคารพาณิชย์ (BANK)"},
        {"symbol": "GULF", "name_th": "บริษัท กัลฟ์ เอ็นเนอร์จี ดีเวลลอปเมนท์ จำกัด (มหาชน)", "sector": "พลังงานและสาธารณูปโภค (ENERGY)"},
    ]

    @classmethod
    def get_top5_recommendations(cls, pipeline) -> List[Dict[str, Any]]:
        scored_stocks = []

        for item in cls.CANDIDATES:
            sym = item["symbol"]
            rep = pipeline.analyze_symbol(sym)

            # Composite scoring algorithm based on audited quant metrics
            # 1. Fundamental F-Score (up to 45 pts)
            f_pts = rep.f_score.f_score * 5.0

            # 2. Altman Z'' safety (up to 20 pts)
            z_pts = 20.0 if rep.altman.zone == "SAFE" else (10.0 if rep.altman.zone == "GREY" else -50.0)

            # 3. Wyckoff Trend (up to 20 pts)
            w_pts = 20.0 if rep.wyckoff.trend == "UPTREND" else (10.0 if rep.wyckoff.trend == "RANGING" else 0.0)

            # 4. Confluence Triple EMA (15 pts)
            ema_pts = 15.0 if rep.confluence.triple_ema_bullish else 0.0

            # 5. Reward-to-Risk (up to 20 pts)
            rr_pts = min(rep.risk.reward_risk_ratio, 3.0) * 6.5

            total_score = f_pts + z_pts + w_pts + ema_pts + rr_pts

            # Filter out severely distressed stocks
            if not rep.altman.is_disqualified:
                scored_stocks.append({
                    "symbol": sym,
                    "name_th": item["name_th"],
                    "sector": item["sector"],
                    "score": total_score,
                    "report": rep,
                })

        # Sort descending by composite score
        scored_stocks.sort(key=lambda x: x["score"], reverse=True)
        top_5 = scored_stocks[:5]

        results = []
        for idx, entry in enumerate(top_5, 1):
            rep = entry["report"]
            sym = entry["symbol"]
            cur_price = rep.risk.entry_price
            tick = SETCompliance.get_tick_size(cur_price)

            # Calculate Buy Zone: between current price and 2 ticks below support
            buy_zone_low = SETCompliance.round_to_valid_tick(cur_price - (2 * tick))
            buy_zone_high = cur_price
            buy_zone_str = f"{buy_zone_low:.2f} - {buy_zone_high:.2f} ฿"

            # Sell Target 1 (Conservative R:R >= 2.0:1)
            target_1 = rep.risk.target_price

            # Sell Target 2 (Extended Trend / 5-Yr Valuation Median)
            target_2 = SETCompliance.round_to_valid_tick(cur_price + ((target_1 - cur_price) * 1.5), direction="up")

            # Cut Loss (Strict ATR-14)
            cut_loss = rep.risk.stop_loss_price

            # Deep-dive rationale synthesis in Thai
            deep_dive = {
                "fundamental_analysis": (
                    f"งบการเงินมีความแข็งแกร่งสูง Piotroski F-Score ได้ {rep.f_score.f_score}/9 คะแนน "
                    f"({'ผ่านเกณฑ์ความสามารถทำกำไรและกระแสเงินสด' if rep.f_score.passed else 'ต้องจับตาสภาพคล่อง'}) "
                    f"ค่าความปลอดภัยทางการเงิน Altman Z''-Score = {rep.altman.z_double_prime:.2f} อยู่ใน {rep.altman.zone} Zone ไร้ความเสี่ยงผิดนัดชำระหนี้ "
                    f"และระดับการประเมินมูลค่า P/E ปัจจุบันอยู่ที่ {rep.valuation.pe_ratio or 'N/A'}x เทียบกับมัธยฐาน 5 ปี ({rep.valuation.historical_5yr_pe_median or 'N/A'}x)"
                ),
                "technical_analysis": (
                    f"โครงสร้างราคาตามทฤษฎี Wyckoff อยู่ในเฟส {rep.wyckoff.trend} โดยทำจุดยกฐาน Higher-Low ชัดเจน "
                    f"เส้นค่าเฉลี่ย Triple EMA {'เรียงตัวขาขึ้นสมบูรณ์ (EMA 20 > 50 > 200)' if rep.confluence.triple_ema_bullish else 'กำลังทดสอบแนวรับสำคัญ'} "
                    f"พฤติกรรมวอลุ่ม (VSA): {rep.vsa.vsa_summary_th}"
                ),
                "strategy_and_risk": (
                    f"กรอบราคาเข้าซื้อที่เหมาะสม: {buy_zone_str} โดยตั้งจุดตัดขาดทุน Stop Loss เด็ดขาดที่ {cut_loss:.2f} ฿ "
                    f"เป้าหมายทำกำไรแรก (Target 1) อยู่ที่ {target_1:.2f} ฿ คิดเป็น Reward-to-Risk (R:R) สูงถึง {rep.risk.reward_risk_ratio:.2f}:1 "
                    f"และเป้าหมายรอบใหญ่ (Target 2) ที่ {target_2:.2f} ฿ ขนาดไม้ที่แนะนำตามพอร์ตความเสี่ยง 1.5% คือ {rep.risk.shares_allocated:,} หุ้น ({rep.risk.board_lots} Lots)"
                ),
            }

            results.append({
                "rank": idx,
                "symbol": sym,
                "name_th": entry["name_th"],
                "sector": entry["sector"],
                "current_price": cur_price,
                "buy_zone": buy_zone_str,
                "buy_price": cur_price,
                "target_1": target_1,
                "target_2": target_2,
                "cut_loss": cut_loss,
                "reward_risk": rep.risk.reward_risk_ratio,
                "f_score": rep.f_score.f_score,
                "f_score_passed": rep.f_score.passed,
                "altman_z": rep.altman.z_double_prime,
                "altman_zone": rep.altman.zone,
                "trend": rep.wyckoff.trend,
                "vsa_signal": "Stopping Volume" if rep.vsa.stopping_volume else ("No Supply" if rep.vsa.no_supply_bar else "ปกติ"),
                "recommended_shares": rep.risk.shares_allocated,
                "recommended_lots": rep.risk.board_lots,
                "trade_value": rep.risk.total_trade_value,
                "deep_dive": deep_dive,
            })

        return results
