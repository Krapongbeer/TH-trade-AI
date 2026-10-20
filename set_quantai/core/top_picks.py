"""SET-QuantAI Top 10 Quantitative Recommendations Engine

Performs full quantitative scanning and deep-dive analysis on the Top 10
Thai equity picks, categorizing them into:
- ควรซื้อ / ทยอยสะสม (BUY / ACCUMULATE)
- ควรขายทำกำไร / ขายลดความเสี่ยง (SELL / TAKE PROFIT)
- ถือรอดูจังหวะ (HOLD)

With real-time current price, recommended buy price, target sell price,
stop loss, upside/downside percentages, and R:R ratios.
"""

from typing import Dict, List, Any
from set_quantai.core.compliance import SETCompliance
from set_quantai.core.models import MarketDirection


class TopPicksEngine:
    CANDIDATES = [
        {"symbol": "PTT", "name_th": "บริษัท ปตท. จำกัด (มหาชน)", "sector": "พลังงานและสาธารณูปโภค (ENERGY)"},
        {"symbol": "CPALL", "name_th": "บริษัท ซีพี ออลล์ จำกัด (มหาชน)", "sector": "พาณิชย์ (COMMERCE)"},
        {"symbol": "DELTA", "name_th": "บริษัท เดลต้า อีเลคโทรนิคส์ (ประเทศไทย) จำกัด (มหาชน)", "sector": "ชิ้นส่วนอิเล็กทรอนิกส์ (ETRON)"},
        {"symbol": "KBANK", "name_th": "ธนาคารกสิกรไทย จำกัด (มหาชน)", "sector": "ธนาคารพาณิชย์ (BANK)"},
        {"symbol": "ADVANC", "name_th": "บริษัท แอดวานซ์ อินโฟร์ เซอร์วิส จำกัด (มหาชน)", "sector": "เทคโนโลยีสารสนเทศและการสื่อสาร (ICT)"},
        {"symbol": "BDMS", "name_th": "บริษัท กรุงเทพดุสิตเวชการ จำกัด (มหาชน)", "sector": "การแพทย์ (HEALTH)"},
        {"symbol": "SCB", "name_th": "เอสซีบี เอกซ์ จำกัด (มหาชน)", "sector": "ธนาคารพาณิชย์ (BANK)"},
        {"symbol": "GULF", "name_th": "บริษัท กัลฟ์ เอ็นเนอร์จี ดีเวลลอปเมนท์ จำกัด (มหาชน)", "sector": "พลังงานและสาธารณูปโภค (ENERGY)"},
        {"symbol": "AOT", "name_th": "บริษัท ท่าอากาศยานไทย จำกัด (มหาชน)", "sector": "ขนส่งและโลจิสติกส์ (TRANS)"},
        {"symbol": "SCC", "name_th": "บริษัท ปูนซิเมนต์ไทย จำกัด (มหาชน)", "sector": "วัสดุก่อสร้าง (CONMAT)"},
        {"symbol": "TRUE", "name_th": "บริษัท ทรู คอร์ปอเรชั่น จำกัด (มหาชน)", "sector": "เทคโนโลยีสารสนเทศและการสื่อสาร (ICT)"},
        {"symbol": "MINT", "name_th": "บริษัท ไมเนอร์ อินเตอร์เนชั่นแนล จำกัด (มหาชน)", "sector": "การท่องเที่ยวและสันทนาการ (TOURISM)"},
        {"symbol": "BBL", "name_th": "ธนาคารกรุงเทพ จำกัด (มหาชน)", "sector": "ธนาคารพาณิชย์ (BANK)"},
        {"symbol": "KTB", "name_th": "ธนาคารกรุงไทย จำกัด (มหาชน)", "sector": "ธนาคารพาณิชย์ (BANK)"},
        {"symbol": "CPN", "name_th": "บริษัท เซ็นทรัลพัฒนา จำกัด (มหาชน)", "sector": "พัฒนาอสังหาริมทรัพย์ (PROP)"},
        {"symbol": "BH", "name_th": "บริษัท โรงพยาบาลบำรุงราษฎร์ จำกัด (มหาชน)", "sector": "การแพทย์ (HEALTH)"},
        {"symbol": "WHA", "name_th": "บริษัท ดับบลิวเอชเอ คอร์ปอเรชั่น จำกัด (มหาชน)", "sector": "พัฒนาอสังหาริมทรัพย์ (PROP)"},
        {"symbol": "CRC", "name_th": "บริษัท เซ็นทรัล รีเทล คอร์ปอเรชั่น จำกัด (มหาชน)", "sector": "พาณิชย์ (COMMERCE)"},
    ]

    @classmethod
    def get_top_recommendations(cls, pipeline, count: int = 10) -> List[Dict[str, Any]]:
        processed_candidates = []

        for item in cls.CANDIDATES:
            sym = item["symbol"]
            rep = pipeline.analyze_symbol(sym)
            quote = pipeline.settrade_client.get_realtime_quote(sym)

            cur_price = quote.get("last", rep.risk.entry_price)
            prev_close = quote.get("prev_close", cur_price)
            change = round(cur_price - prev_close, 2)
            pct_change = round((change / prev_close) * 100, 2) if prev_close > 0 else 0.0

            tick = SETCompliance.get_tick_size(cur_price)
            buy_zone_low = SETCompliance.round_to_valid_tick(cur_price - (2 * tick))
            buy_zone_high = cur_price
            buy_zone_str = f"{buy_zone_low:.2f} - {buy_zone_high:.2f} ฿"

            target_1 = rep.risk.target_price
            target_2 = SETCompliance.round_to_valid_tick(cur_price + ((target_1 - cur_price) * 1.5), direction="up")
            cut_loss = rep.risk.stop_loss_price

            upside_pct = round(((target_1 - cur_price) / cur_price) * 100, 2) if cur_price > 0 else 0.0
            downside_pct = round(((cur_price - cut_loss) / cur_price) * 100, 2) if cur_price > 0 else 0.0

            is_uptrend = rep.wyckoff.trend == "UPTREND"
            is_distress = rep.altman.zone == "DISTRESS"

            # Determine Action
            if (rep.ai_explainer.decision.value == "BUY" or is_uptrend) and rep.f_score.f_score >= 5 and not is_distress and upside_pct >= 6.5:
                action = "BUY"
                action_th = "ควรซื้อ (STRONG BUY)"
                action_badge = "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                action_reason = f"กราฟขาขึ้นแข็งแกร่ง มีแรงซื้อสะสมต่อเนื่อง Upside สูงถึง +{upside_pct}% คุ้มค่าความเสี่ยง"
                score = rep.f_score.f_score * 5.0 + rep.risk.reward_risk_ratio * 7.0 + 30.0
            elif not is_distress and upside_pct >= 4.5 and rep.risk.reward_risk_ratio >= 1.7:
                action = "ACCUMULATE"
                action_th = "ทยอยสะสม (ACCUMULATE)"
                action_badge = "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                action_reason = f"ราคาพักตัวสะสมแรงในแนวรับ แนะนำทยอยรับเมื่อย่อตัว (Upside +{upside_pct}%)"
                score = rep.f_score.f_score * 5.0 + rep.risk.reward_risk_ratio * 6.0 + 20.0
            elif is_distress or upside_pct < 4.0 or rep.risk.reward_risk_ratio < 1.5 or rep.wyckoff.trend == "DOWNTREND":
                action = "SELL"
                action_th = "ควรขายทำกำไร / ขายลดพอร์ต (SELL)"
                action_badge = "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                action_reason = "ราคาใกล้ชนเป้าหมายแนวต้านหลัก หรือเริ่มมีความเสี่ยง แนะนำขายทำกำไรล็อกผลตอบแทน"
                score = 50.0 - upside_pct
            else:
                action = "HOLD"
                action_th = "ถือรอดู (HOLD)"
                action_badge = "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                action_reason = "ราคากำลังแกว่งตัวในกรอบ ควรรอย่อตัวใกล้แนวรับหรือรอสัญญาณเบรกเอาต์"
                score = 30.0

            processed_candidates.append({
                "symbol": sym,
                "name_th": item["name_th"],
                "sector": item["sector"],
                "current_price": cur_price,
                "change": change,
                "pct_change": pct_change,
                "action": action,
                "action_th": action_th,
                "action_badge": action_badge,
                "action_reason": action_reason,
                "buy_price": cur_price,
                "buy_zone": buy_zone_str,
                "target_1": target_1,
                "target_2": target_2,
                "cut_loss": cut_loss,
                "upside_pct": upside_pct,
                "downside_pct": downside_pct,
                "reward_risk": rep.risk.reward_risk_ratio,
                "f_score": rep.f_score.f_score,
                "altman_zone": rep.altman.zone,
                "trend": rep.wyckoff.trend,
                "recommended_shares": rep.risk.shares_allocated or 1000,
                "recommended_lots": rep.risk.board_lots or 10,
                "trade_value": rep.risk.total_trade_value,
                "score": score,
            })

        # Combine top buys and top sells to guarantee balanced visibility
        buys = sorted([s for s in processed_candidates if s["action"] in ("BUY", "ACCUMULATE")], key=lambda x: x["score"], reverse=True)
        sells = sorted([s for s in processed_candidates if s["action"] in ("SELL", "HOLD")], key=lambda x: x["score"], reverse=True)

        top_buys = buys[:7]
        top_sells = sells[:3]
        final_list = top_buys + top_sells
        if len(final_list) < count:
            remaining = [s for s in processed_candidates if s not in final_list]
            final_list.extend(remaining[:count - len(final_list)])

        for idx, item in enumerate(final_list, 1):
            item["rank"] = idx

        return final_list[:count]

    @classmethod
    def get_top5_recommendations(cls, pipeline) -> List[Dict[str, Any]]:
        # Backwards compatibility for existing auto-trade runner
        return cls.get_top_recommendations(pipeline, count=5)
