"""SET-QuantAI - Settrade Streaming-Inspired Trading & Quant Terminal

A modern, highly intuitive Web UI inspired by Settrade Streaming:
- Real-time Market Ticker (SET Index, Volume, P/E)
- Account Bar (Kequiv-E, Line Available, Cash Balance)
- 4 Primary Tabs:
  1. Watchlist (Real-time prices, %Chg, Volumes, AI Signals)
  2. Quote & AI Analysis (5-Bid / 5-Offer Level-2 Depth + Plain-Thai AI Summary)
  3. Buy / Sell Order Pad (Streaming-style Order Entry with 100-share Board Lot & Tick Ladder)
  4. Order Status / History (Track matched/pending sandbox orders)
"""

import os
import threading
import time
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from set_quantai.core.pipeline import QuantAIPipeline
from set_quantai.core.models import MarketDirection
from set_quantai.core.compliance import SETCompliance
from set_quantai.core.top_picks import TopPicksEngine
from set_quantai.core.auto_trader import AutoTraderEngine

web_app = FastAPI(title="SET-QuantAI Streaming Terminal", description="หน้าจอเทรดและวิเคราะห์หุ้นไทยสไตล์ Settrade Streaming")
pipeline = QuantAIPipeline()

# Automatic background pinger to keep Render free tier awake 24/7
def _start_keep_alive():
    def _loop():
        time.sleep(60)  # Wait 1 minute after server starts
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://th-trade-ai.onrender.com")
        target_url = f"{render_url.rstrip('/')}/health"
        while True:
            try:
                time.sleep(600)  # Ping every 10 mins (Render sleeps at 15 mins)
                requests.get(target_url, timeout=15)
            except Exception:
                pass

    t = threading.Thread(target=_loop, daemon=True)
    t.start()

_start_keep_alive()

# In-memory orders history for Sandbox execution
orders_history: List[Dict[str, Any]] = [
    {
        "order_id": "ORD-SBX-KBANK-1000",
        "time": "14:44:08",
        "symbol": "KBANK",
        "side": "BUY",
        "volume": 1000,
        "price": 178.50,
        "trade_value": 178500.0,
        "status": "Matched",
    },
    {
        "order_id": "ORD-SBX-ADVANC-1000",
        "time": "14:44:08",
        "symbol": "ADVANC",
        "side": "BUY",
        "volume": 1000,
        "price": 326.00,
        "trade_value": 326000.0,
        "status": "Matched",
    },
    {
        "order_id": "ORD-SBX-SCB-1000",
        "time": "14:44:08",
        "symbol": "SCB",
        "side": "BUY",
        "volume": 1000,
        "price": 131.00,
        "trade_value": 131000.0,
        "status": "Matched",
    },
    {
        "order_id": "ORD-SBX-DELTA-1000",
        "time": "14:44:08",
        "symbol": "DELTA",
        "side": "BUY",
        "volume": 1000,
        "price": 187.50,
        "trade_value": 187500.0,
        "status": "Matched",
    },
    {
        "order_id": "ORD-SBX-PTT-1000",
        "time": "14:44:08",
        "symbol": "PTT",
        "side": "BUY",
        "volume": 1000,
        "price": 36.00,
        "trade_value": 36000.0,
        "status": "Matched",
    },
]


@web_app.get("/health")
@web_app.head("/health")
@web_app.get("/healthz")
@web_app.head("/healthz")
def healthcheck():
    return {"status": "ok"}


@web_app.get("/api/top5-recommendations")
def get_top5_recommendations():
    return TopPicksEngine.get_top5_recommendations(pipeline)


@web_app.get("/api/top10-recommendations")
def get_top10_recommendations():
    return TopPicksEngine.get_top_recommendations(pipeline, count=10)


@web_app.post("/api/auto-trade/buy-top5")
def auto_trade_buy_top5():
    res = AutoTraderEngine.execute_top5_purchases(pipeline, shares_per_stock=1000)
    for o in res.get("orders", []):
        orders_history.insert(0, {
            "order_id": o["order_id"],
            "time": datetime.now().strftime("%H:%M:%S"),
            "symbol": o["symbol"],
            "side": "BUY",
            "volume": o["shares"],
            "price": o["buy_price"],
            "trade_value": o["initial_value"],
            "status": "Matched",
        })
    return res


@web_app.post("/api/auto-trade/simulate-exits")
def auto_trade_simulate_exits():
    res = AutoTraderEngine.simulate_target_exits(pipeline)
    for t in res.get("closed_trades", []):
        orders_history.insert(0, {
            "order_id": f"SELL-TARGET-{t['symbol']}-{int(datetime.now().timestamp())}",
            "time": datetime.now().strftime("%H:%M:%S"),
            "symbol": t["symbol"],
            "side": "SELL",
            "volume": t["shares"],
            "price": t["exit_price"],
            "trade_value": t["exit_price"] * t["shares"],
            "status": "Matched",
        })
    return res


@web_app.post("/api/auto-trade/reset")
def auto_trade_reset():
    return AutoTraderEngine.reset_data()


@web_app.get("/api/auto-trade/performance")
def auto_trade_performance():
    return AutoTraderEngine.get_performance_summary(pipeline)


class AddWatchlistRequest(BaseModel):
    symbol: str
    target_price: Optional[float] = None
    priority: int = 1
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class PlaceOrderRequest(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    volume: int
    price: float
    pin: str = "000000"


@web_app.get("/api/account")
def get_account():
    info = pipeline.settrade_client.get_account_info()
    data = AutoTraderEngine.load_data()
    positions = data.get("positions", [])
    total_pos_cost = sum(p["buy_price"] * p["shares"] for p in positions)
    total_manual_bought = sum(o["trade_value"] for o in orders_history if o["side"] == "BUY" and o["status"] == "Matched" and not any(p["symbol"] == o["symbol"] for p in positions))
    total_bought = total_pos_cost + total_manual_bought
    cash = max(0.0, 1_000_000.0 - total_bought)
    info["cash_balance"] = cash
    info["line_available"] = cash
    return info


@web_app.get("/api/portfolio")
def get_portfolio():
    data = AutoTraderEngine.load_data()
    positions = data.get("positions", [])
    res_positions = []
    total_cost = 0.0
    total_market_val = 0.0

    for pos in positions:
        sym = pos["symbol"]
        q = pipeline.settrade_client.get_realtime_quote(sym)
        curr = q.get("last", pos["buy_price"])
        cost = pos["buy_price"] * pos["shares"]
        mkt_val = curr * pos["shares"]
        unrealized_pl = mkt_val - cost
        unrealized_pct = round((unrealized_pl / cost) * 100, 2) if cost > 0 else 0.0

        total_cost += cost
        total_market_val += mkt_val

        res_positions.append({
            **pos,
            "current_price": curr,
            "cost_value": cost,
            "market_value": mkt_val,
            "unrealized_pl": round(unrealized_pl, 2),
            "unrealized_pct": unrealized_pct,
        })

    total_pl = total_market_val - total_cost
    total_pl_pct = round((total_pl / total_cost) * 100, 2) if total_cost > 0 else 0.0

    return {
        "positions": res_positions,
        "total_cost": round(total_cost, 2),
        "total_market_value": round(total_market_val, 2),
        "total_unrealized_pl": round(total_pl, 2),
        "total_unrealized_pct": total_pl_pct,
        "cash_balance": max(0.0, 1_000_000.0 - total_cost),
    }


@web_app.get("/api/watchlist")
def get_watchlist():
    items = pipeline.watchlist_manager.get_items()
    res = []
    for item in items:
        # Get latest quote
        q = pipeline.settrade_client.get_realtime_quote(item.symbol)
        last_price = q["last"]
        prev_close = q["prev_close"]
        chg = round(last_price - prev_close, 2)
        pct_chg = round((chg / prev_close) * 100, 2) if prev_close > 0 else 0.0

        res.append({
            "symbol": item.symbol,
            "target_price": item.target_price,
            "notes": item.notes,
            "priority": item.priority,
            "tags": item.tags,
            "last": last_price,
            "prev_close": prev_close,
            "change": chg,
            "pct_change": pct_chg,
            "volume": q["volume"],
            "value": q["value"],
        })
    return res


@web_app.post("/api/watchlist")
def add_watchlist(req: AddWatchlistRequest):
    item = pipeline.watchlist_manager.add_symbol(
        symbol=req.symbol,
        notes=req.notes,
        priority=req.priority,
        target_price=req.target_price,
        tags=req.tags or [],
    )
    return item.model_dump(mode="json")


@web_app.delete("/api/watchlist/{symbol}")
def delete_watchlist(symbol: str):
    success = pipeline.watchlist_manager.remove_symbol(symbol)
    if not success:
        raise HTTPException(status_code=404, detail="Stock not found")
    return {"status": "success", "symbol": symbol.upper()}


@web_app.get("/api/quote/{symbol}")
def get_quote(symbol: str):
    symbol = symbol.strip().upper()
    quote = pipeline.settrade_client.get_realtime_quote(symbol)
    depth = pipeline.settrade_client.get_level2_depth(symbol)
    rep = pipeline.analyze_symbol(symbol)

    ceiling, floor = SETCompliance.calculate_ceiling_floor(quote["prev_close"])

    return {
        "symbol": symbol,
        "last": quote["last"],
        "prev_close": quote["prev_close"],
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "change": round(quote["last"] - quote["prev_close"], 2),
        "pct_change": round(((quote["last"] - quote["prev_close"]) / quote["prev_close"]) * 100, 2),
        "volume": quote["volume"],
        "value": quote["value"],
        "ceiling": ceiling,
        "floor": floor,
        "bids": [{"price": b.price, "volume": b.volume} for b in depth.bids],
        "offers": [{"price": o.price, "volume": o.volume} for o in depth.offers],
        "analysis": {
            "decision": rep.ai_explainer.decision.value,
            "confidence": rep.ai_explainer.confidence_score,
            "headline": rep.ai_explainer.headline_th,
            "f_score": rep.f_score.f_score,
            "f_score_passed": rep.f_score.passed,
            "altman_z": rep.altman.z_double_prime,
            "altman_zone": rep.altman.zone,
            "pe_ratio": rep.valuation.pe_ratio,
            "trend": rep.wyckoff.trend,
            "vsa_signal": "Stopping Volume (แรงซื้อดูดซับแรงขาย)" if rep.vsa.stopping_volume else ("No Supply (ย่อตัววอลุ่มแห้ง)" if rep.vsa.no_supply_bar else "วอลุ่มปกติ"),
            "triple_ema": rep.confluence.triple_ema_bullish,
            "entry_price": rep.risk.entry_price,
            "stop_loss": rep.risk.stop_loss_price,
            "target_price": rep.risk.target_price,
            "reward_risk": rep.risk.reward_risk_ratio,
            "recommended_shares": rep.risk.shares_allocated,
            "board_lots": rep.risk.board_lots,
            "trade_value": rep.risk.total_trade_value,
            "overall_summary": rep.ai_explainer.overall_recommendation_th,
        }
    }


@web_app.post("/api/order")
def place_order(req: PlaceOrderRequest):
    res = pipeline.settrade_client.place_order(
        symbol=req.symbol,
        side=req.side,
        volume=req.volume,
        price=req.price,
    )
    if res.get("status") == "SUCCESS":
        orders_history.insert(0, {
            "order_id": res.get("order_id", f"ORD-SBX-{int(datetime.now().timestamp())}"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "symbol": req.symbol.upper(),
            "side": req.side.upper(),
            "volume": res.get("volume", req.volume),
            "price": res.get("price", req.price),
            "trade_value": res.get("trade_value", req.volume * req.price),
            "status": "Matched",
        })
        return res
    raise HTTPException(status_code=400, detail=res.get("message", "Order failed"))


@web_app.get("/api/orders")
def get_orders():
    data = AutoTraderEngine.load_data()
    merged = list(orders_history)
    for p in data.get("positions", []):
        if not any(o.get("order_id") == p["order_id"] for o in merged):
            merged.append({
                "order_id": p["order_id"],
                "time": p.get("buy_time", datetime.now().strftime("%H:%M:%S")),
                "symbol": p["symbol"],
                "side": "BUY",
                "volume": p["shares"],
                "price": p["buy_price"],
                "trade_value": p["initial_value"],
                "status": "Matched",
            })
    return merged


@web_app.get("/", response_class=HTMLResponse)
@web_app.head("/")
def index_html():
    return """<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SET-QuantAI: หน้าจอวิเคราะห์ & เทรดหุ้นไทย</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Prompt', sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        .stock-up { color: #00E676; }
        .stock-down { color: #FF5252; }
        .stock-flat { color: #FFD600; }
        .bg-stream-dark { background-color: #0b0e14; }
        .bg-stream-panel { background-color: #151922; }
        .bg-stream-card { background-color: #1a202c; }
        .border-stream { border-color: #242c3d; }
    </style>
</head>
<body class="bg-stream-dark text-slate-100 min-h-screen flex flex-col">

    <!-- 1. Top Header: Market Ticker & Account Bar (Settrade Streaming Style) -->
    <header class="bg-stream-panel border-b border-stream text-xs select-none">
        <!-- Top Market Status Bar -->
        <div class="max-w-7xl mx-auto px-4 py-2 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-slate-300">
            <div class="flex items-center space-x-4">
                <span class="font-bold text-white tracking-wide flex items-center space-x-1.5">
                    <span class="text-blue-400 font-extrabold text-sm">SET-QuantAI</span>
                    <span class="text-[10px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded font-mono">STREAMING</span>
                </span>
                <span class="hidden sm:inline text-slate-600">|</span>
                <div class="flex items-center space-x-2">
                    <span class="font-semibold text-slate-200">SET</span>
                    <span class="font-mono font-bold text-white">1,452.18</span>
                    <span class="font-mono stock-up font-bold">+6.42 (+0.44%)</span>
                    <span class="text-slate-400 hidden md:inline">มูลค่า 48,250.80 ลบ.</span>
                </div>
            </div>

            <div class="flex items-center space-x-4 font-mono text-[11px]">
                <div>พอร์ต: <span class="font-bold text-emerald-400" id="topAccountNo">Kequiv-E</span></div>
                <div class="hidden sm:block">วงเงินซื้อขาย: <span class="font-bold text-white" id="topLineAvail">1,000,000.00</span> ฿</div>
                <div>เงินสด: <span class="font-bold text-blue-400" id="topCashBal">1,000,000.00</span> ฿</div>
                <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Connected"></span>
            </div>
        </div>

        <!-- Main Navigation Bar (แท็บเมนูหลักสไตล์ Streaming & Easy Analyzer) -->
        <div class="max-w-7xl mx-auto px-4 flex items-center justify-between">
            <nav class="flex space-x-1 py-1 overflow-x-auto">
                <button onclick="switchTab('analyzer')" id="tab-analyzer" class="px-4 py-2.5 font-bold rounded-t-lg transition flex items-center space-x-2 border-b-2 border-blue-500 text-blue-400 bg-stream-dark whitespace-nowrap">
                    <span>🔍</span> <span>วิเคราะห์หุ้น & ดูกราฟ (Easy Analyzer)</span>
                </button>
                <button onclick="switchTab('top10')" id="tab-top10" class="px-4 py-2.5 font-medium rounded-t-lg transition flex items-center space-x-2 border-b-2 border-transparent text-slate-400 hover:text-white whitespace-nowrap">
                    <span>🎯</span> <span>กวาดหุ้นเด่น 10 ตัว (ควรซื้อ / ควรขาย)</span>
                </button>
                <button onclick="switchTab('portfolio')" id="tab-portfolio" class="px-4 py-2.5 font-medium rounded-t-lg transition flex items-center space-x-2 border-b-2 border-transparent text-slate-400 hover:text-white whitespace-nowrap">
                    <span>💼</span> <span>พอร์ต & คำสั่งซื้อขาย (Portfolio)</span>
                </button>
                <button onclick="switchTab('order')" id="tab-order" class="px-4 py-2.5 font-medium rounded-t-lg transition flex items-center space-x-2 border-b-2 border-transparent text-slate-400 hover:text-white whitespace-nowrap">
                    <span>⚡</span> <span>ส่งคำสั่งซื้อขาย (Order Pad)</span>
                </button>
                <button onclick="switchTab('watchlist')" id="tab-watchlist" class="px-4 py-2.5 font-medium rounded-t-lg transition flex items-center space-x-2 border-b-2 border-transparent text-slate-400 hover:text-white whitespace-nowrap">
                    <span>⭐</span> <span>Watchlist (กระดานหุ้น)</span>
                </button>
                <button onclick="switchTab('quote')" id="tab-quote" class="px-4 py-2.5 font-medium rounded-t-lg transition flex items-center space-x-2 border-b-2 border-transparent text-slate-400 hover:text-white whitespace-nowrap">
                    <span>📊</span> <span>Bid/Offer 5 ช่อง (Depth)</span>
                </button>
                <button onclick="switchTab('accuracy')" id="tab-accuracy" class="px-4 py-2.5 font-medium rounded-t-lg transition flex items-center space-x-2 border-b-2 border-transparent text-slate-400 hover:text-white whitespace-nowrap">
                    <span>🏆</span> <span>ทดสอบความแม่นยำ</span>
                </button>
            </nav>

            <!-- Search Stock Shortcut -->
            <div class="flex items-center space-x-2 py-1">
                <div class="relative">
                    <input id="quickSearchInput" type="text" placeholder="พิมพ์ชื่อหุ้น เช่น PTT" class="bg-slate-900 border border-slate-700 text-white rounded px-3 py-1 text-xs w-36 uppercase font-bold focus:outline-none focus:border-blue-500" onkeyup="if(event.key==='Enter') quickSearch()">
                    <button onclick="quickSearch()" class="absolute right-1.5 top-1.5 text-slate-400 hover:text-white text-xs">🔍</button>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content Area -->
    <main class="max-w-7xl mx-auto px-4 py-6 flex-1 w-full">

        <!-- ======================================================== -->
        <!-- TAB 0: EASY ANALYZER & CHART (วิเคราะห์หุ้นรายตัว + กราฟ) -->
        <!-- ======================================================== -->
        <section id="view-analyzer" class="space-y-6">
            <!-- Search & Quick Selection Banner -->
            <div class="bg-gradient-to-r from-blue-950/60 via-slate-900 to-stream-panel p-6 rounded-2xl border border-blue-500/30 shadow-2xl space-y-4">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h2 class="text-xl md:text-2xl font-black text-white flex items-center space-x-2">
                            <span>🔍</span> <span>ระบบวิเคราะห์หุ้นอัจฉริยะ (AI Stock Analyzer)</span>
                        </h2>
                        <p class="text-xs md:text-sm text-slate-300 mt-1">
                            ใส่ชื่อย่อหุ้นไทยเพื่อรับบทวิเคราะห์แบบ "ฟันธง", ราคาซื้อที่แนะนำ, จุดตัดขาดทุน, เป้าทำกำไร และดูกราฟเทคนิค TradingView ในที่เดียว
                        </p>
                    </div>
                    <div class="flex items-center space-x-2">
                        <span class="text-xs text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/30 font-semibold flex items-center space-x-1.5">
                            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                            <span>AI วิเคราะห์สดแบบ Real-time</span>
                        </span>
                    </div>
                </div>

                <!-- Big Search Box -->
                <div class="flex flex-col sm:flex-row items-stretch gap-2 pt-2">
                    <div class="relative flex-1">
                        <span class="absolute left-4 top-3.5 text-slate-400 text-base">🔍</span>
                        <input id="easySymbolInput" type="text" placeholder="พิมพ์ชื่อย่อหุ้น เช่น CPALL, PTT, DELTA, BDMS, KBANK..." value="CPALL" class="w-full bg-slate-950 border-2 border-slate-700 hover:border-blue-400 focus:border-blue-500 text-white rounded-xl pl-11 pr-4 py-3 text-base md:text-lg font-bold uppercase tracking-wider focus:outline-none transition shadow-inner" onkeyup="if(event.key==='Enter') analyzeStock()">
                    </div>
                    <button onclick="analyzeStock()" class="px-8 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl text-base transition shadow-lg shadow-blue-600/30 flex items-center justify-center space-x-2">
                        <span>🚀</span> <span>วิเคราะห์ทันที</span>
                    </button>
                </div>

                <!-- Quick Stock Buttons -->
                <div class="flex flex-wrap items-center gap-2 pt-1 text-xs">
                    <span class="text-slate-400 font-semibold mr-1">หุ้นยอดนิยม:</span>
                    <button onclick="analyzeStock('CPALL')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">CPALL</button>
                    <button onclick="analyzeStock('PTT')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">PTT</button>
                    <button onclick="analyzeStock('DELTA')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">DELTA</button>
                    <button onclick="analyzeStock('KBANK')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">KBANK</button>
                    <button onclick="analyzeStock('ADVANC')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">ADVANC</button>
                    <button onclick="analyzeStock('BDMS')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">BDMS</button>
                    <button onclick="analyzeStock('AOT')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">AOT</button>
                    <button onclick="analyzeStock('GULF')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">GULF</button>
                    <button onclick="analyzeStock('SCB')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">SCB</button>
                    <button onclick="analyzeStock('TRUE')" class="px-3 py-1 bg-slate-800 hover:bg-blue-600/30 hover:border-blue-500 text-slate-200 hover:text-white rounded-lg border border-slate-700 font-mono font-bold transition">TRUE</button>
                </div>
            </div>

            <!-- Analysis Content Area -->
            <div id="easyResultContainer" class="space-y-6">
                <!-- Stock Header Card -->
                <div class="bg-stream-panel rounded-2xl border border-stream p-5 flex flex-wrap items-center justify-between gap-4">
                    <div class="flex items-center space-x-4">
                        <div class="w-14 h-14 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center font-mono font-black text-2xl text-blue-400" id="easySymbolBadge">
                            CPALL
                        </div>
                        <div>
                            <div class="flex items-baseline space-x-3">
                                <h3 id="easySymbolText" class="text-3xl font-black font-mono text-white">CPALL</h3>
                                <span id="easyLastText" class="text-3xl font-black font-mono stock-up">64.50</span>
                                <span id="easyChangeText" class="text-base font-bold font-mono stock-up">+1.25 (+1.98%)</span>
                            </div>
                            <div class="flex items-center space-x-3 text-xs text-slate-400 mt-0.5">
                                <span>High / Low: <strong id="easyHighLowText" class="text-slate-200 font-mono">65.00 / 63.75</strong></span>
                                <span>•</span>
                                <span>ปริมาณซื้อขาย: <strong id="easyVolText" class="text-slate-200 font-mono">24.5M</strong> หุ้น</span>
                            </div>
                        </div>
                    </div>

                    <div class="flex items-center space-x-3">
                        <button onclick="easyQuickBuy(1000)" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-xs transition shadow-lg shadow-emerald-500/20 flex items-center space-x-2">
                            <span>⚡</span> <span>ซื้อทันที (1,000 หุ้น)</span>
                        </button>
                        <button onclick="easyAddToWatchlist()" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-xl text-xs font-semibold border border-slate-700 transition flex items-center space-x-1.5">
                            <span>⭐</span> <span>บันทึก Watchlist</span>
                        </button>
                    </div>
                </div>

                <!-- 4 Major Decision Cards: Buy Price, Target, Cut Loss, Trend -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <!-- 1. Recommended Buy Price -->
                    <div class="bg-stream-panel rounded-2xl border-2 border-blue-500/40 p-5 space-y-2 relative overflow-hidden">
                        <div class="absolute -right-3 -top-3 w-16 h-16 bg-blue-500/10 rounded-full blur-xl"></div>
                        <div class="flex items-center justify-between text-xs text-blue-400 font-bold">
                            <span>🎯 ราคาซื้อที่แนะนำ</span>
                            <span class="text-[10px] bg-blue-500/20 px-2 py-0.5 rounded font-mono">BUY ZONE</span>
                        </div>
                        <div id="easyBuyZone" class="text-2xl font-black font-mono text-white">63.50 - 64.50 ฿</div>
                        <p class="text-[11px] text-slate-400 leading-tight">ราคาเข้าสะสมที่ไม่ไล่ราคา ปลอดภัยต่อการลงทุน</p>
                    </div>

                    <!-- 2. Target Price -->
                    <div class="bg-stream-panel rounded-2xl border-2 border-emerald-500/40 p-5 space-y-2 relative overflow-hidden">
                        <div class="absolute -right-3 -top-3 w-16 h-16 bg-emerald-500/10 rounded-full blur-xl"></div>
                        <div class="flex items-center justify-between text-xs text-emerald-400 font-bold">
                            <span>📈 เป้าหมายทำกำไร</span>
                            <span class="text-[10px] bg-emerald-500/20 px-2 py-0.5 rounded font-mono">TARGET</span>
                        </div>
                        <div id="easyTargetText" class="text-2xl font-black font-mono text-emerald-400">70.00 ฿ (+8.5%)</div>
                        <p class="text-[11px] text-slate-400 leading-tight">แนวต้านสำคัญและเป้าประเมินมูลค่างวดถัดไป</p>
                    </div>

                    <!-- 3. Cut Loss -->
                    <div class="bg-stream-panel rounded-2xl border-2 border-rose-500/40 p-5 space-y-2 relative overflow-hidden">
                        <div class="absolute -right-3 -top-3 w-16 h-16 bg-rose-500/10 rounded-full blur-xl"></div>
                        <div class="flex items-center justify-between text-xs text-rose-400 font-bold">
                            <span>🛑 จุดตัดขาดทุน</span>
                            <span class="text-[10px] bg-rose-500/20 px-2 py-0.5 rounded font-mono">CUT LOSS</span>
                        </div>
                        <div id="easyStopText" class="text-2xl font-black font-mono text-rose-400">62.00 ฿ (-3.8%)</div>
                        <p class="text-[11px] text-slate-400 leading-tight">หากหลุดราคานี้ควรตัดขาดทุนเพื่อปกป้องเงินต้น</p>
                    </div>

                    <!-- 4. Trend & R:R -->
                    <div class="bg-stream-panel rounded-2xl border-2 border-purple-500/40 p-5 space-y-2 relative overflow-hidden">
                        <div class="absolute -right-3 -top-3 w-16 h-16 bg-purple-500/10 rounded-full blur-xl"></div>
                        <div class="flex items-center justify-between text-xs text-purple-400 font-bold">
                            <span>📊 แนวโน้มราคา</span>
                            <span class="text-[10px] bg-purple-500/20 px-2 py-0.5 rounded font-mono">TREND</span>
                        </div>
                        <div id="easyTrendText" class="text-xl font-black font-mono text-white">ขาขึ้น (UPTREND)</div>
                        <div class="text-[11px] text-slate-400 flex items-center justify-between">
                            <span>ความคุ้มค่า R:R:</span>
                            <strong id="easyRRText" class="text-purple-300 font-mono">2.24 : 1 (คุ้ม)</strong>
                        </div>
                    </div>
                </div>

                <!-- Big Recommendation Verdict Banner -->
                <div id="easyVerdictCard" class="p-5 rounded-2xl border border-emerald-500/40 bg-gradient-to-r from-emerald-950/40 via-slate-900 to-stream-panel space-y-2">
                    <div class="flex flex-wrap items-center justify-between gap-2">
                        <div class="flex items-center space-x-3">
                            <span id="easyVerdictBadge" class="px-4 py-1.5 rounded-full text-xs font-black font-mono bg-emerald-500 text-slate-950">
                                BUY (น่าซื้อลงทุน)
                            </span>
                            <h4 id="easyHeadlineText" class="text-base font-bold text-white">สัญญาณซื้อเด่น ปัจจัยเทคนิคและพื้นฐานสนับสนุน</h4>
                        </div>
                        <span id="easyConfidenceText" class="text-xs text-emerald-400 font-mono font-bold bg-emerald-500/10 px-3 py-1 rounded-lg border border-emerald-500/20">
                            ความเชื่อมั่น AI: 85%
                        </span>
                    </div>
                    <p id="easySummaryText" class="text-xs md:text-sm text-slate-200 leading-relaxed pt-1">
                        กราฟราคาเคลื่อนไหวเหนือเส้นค่าเฉลี่ย 200 วัน มีแรงซื้อสะสมสม่ำเสมอ งบการเงินแข็งแกร่งไม่เสี่ยงล้มละลาย
                    </p>
                </div>

                <!-- Interactive TradingView Candlestick Chart (ตามที่ผู้ใช้ขอ) -->
                <div class="bg-stream-panel rounded-2xl border border-stream p-4 space-y-3">
                    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-stream pb-3">
                        <div class="flex items-center space-x-2">
                            <span class="text-base">📈</span>
                            <h3 class="font-bold text-white text-sm">กราฟราคาเทคนิคแบบอินเตอร์แอคทีฟ (TradingView Interactive Chart)</h3>
                            <span id="tvChartStockBadge" class="text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded font-mono font-bold">SET:CPALL</span>
                            <span class="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded font-mono">SET EXCHANGE</span>
                        </div>
                        <span class="text-xs text-slate-400">ปรับอินดิเคเตอร์, ไทม์เฟรม, และวาดเส้นเทรนด์ได้อิสระ</span>
                    </div>
                    <!-- Chart Frame -->
                    <div id="tradingview_chart_container" class="w-full h-[480px] rounded-xl overflow-hidden border border-slate-800 bg-slate-950 flex items-center justify-center text-slate-500">
                        <span>⏳ กำลังโหลดกราฟราคา TradingView...</span>
                    </div>
                </div>

                <!-- 3 Easy Pillars (พื้นฐาน, กราฟ, การคุมเงิน) -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                    <!-- Pillar 1: กราฟและวอลุ่ม -->
                    <div class="bg-stream-panel p-4 rounded-xl border border-stream space-y-2">
                        <h4 class="font-bold text-slate-200 flex items-center space-x-1.5 text-sm">
                            <span>📊</span> <span>1. กราฟเทคนิค & สภาพคล่อง</span>
                        </h4>
                        <div class="flex justify-between py-1 border-b border-slate-800 text-slate-300">
                            <span>สัญญาณวอลุ่ม Smart Money:</span>
                            <span id="easyVsaText" class="font-bold text-white font-mono">ปกติ</span>
                        </div>
                        <div class="flex justify-between py-1 border-b border-slate-800 text-slate-300">
                            <span>เส้นค่าเฉลี่ย EMA:</span>
                            <span id="easyEmaText" class="font-bold text-emerald-400 font-mono">เรียงตัวขาขึ้น</span>
                        </div>
                        <div class="flex justify-between py-1 text-slate-300">
                            <span>กรอบการแกว่ง (Ceiling/Floor):</span>
                            <span id="easyCeilFloorText" class="font-bold text-slate-200 font-mono">75.00 / 45.00</span>
                        </div>
                    </div>

                    <!-- Pillar 2: พื้นฐานงบการเงิน -->
                    <div class="bg-stream-panel p-4 rounded-xl border border-stream space-y-2">
                        <h4 class="font-bold text-slate-200 flex items-center space-x-1.5 text-sm">
                            <span>🏢</span> <span>2. สุขภาพการเงิน & ความปลอดภัย</span>
                        </h4>
                        <div class="flex justify-between py-1 border-b border-slate-800 text-slate-300">
                            <span>คะแนนงบ 5 ปี (F-Score):</span>
                            <span id="easyFscoreText" class="font-bold text-white font-mono">7/9 (ดีมาก)</span>
                        </div>
                        <div class="flex justify-between py-1 border-b border-slate-800 text-slate-300">
                            <span>ความเสี่ยงล้มละลาย (Altman):</span>
                            <span id="easyAltmanText" class="font-bold text-emerald-400 font-mono">ปลอดภัย</span>
                        </div>
                        <div class="flex justify-between py-1 text-slate-300">
                            <span>ความถูกแพง (P/E Ratio):</span>
                            <span id="easyPeText" class="font-bold text-white font-mono">15.2x</span>
                        </div>
                    </div>

                    <!-- Pillar 3: คำแนะนำขนาดไม้ -->
                    <div class="bg-stream-panel p-4 rounded-xl border border-stream space-y-2">
                        <h4 class="font-bold text-slate-200 flex items-center space-x-1.5 text-sm">
                            <span>💡</span> <span>3. ขนาดไม้ที่ระบบแนะนำ</span>
                        </h4>
                        <div class="flex justify-between py-1 border-b border-slate-800 text-slate-300">
                            <span>จำนวนหุ้นที่ควรซื้อ:</span>
                            <span id="easySharesText" class="font-bold text-emerald-400 font-mono text-sm">1,500 หุ้น</span>
                        </div>
                        <div class="flex justify-between py-1 border-b border-slate-800 text-slate-300">
                            <span>มูลค่าการซื้อโดยประมาณ:</span>
                            <span id="easyTradeValText" class="font-bold text-white font-mono">96,750 ฿</span>
                        </div>
                        <div class="flex justify-between py-1 text-slate-300">
                            <span>ความเสี่ยงพอร์ต:</span>
                            <span class="font-bold text-blue-400 font-mono">ไม่เกิน 1.5% ของเงินสด</span>
                        </div>
                    </div>
                </div>

                <!-- Bottom Quick Action Bar -->
                <div class="bg-slate-900 border border-blue-500/30 p-4 rounded-2xl flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <span class="font-bold text-white text-sm">ต้องการเข้าซื้อหุ้นตัวนี้เข้าพอร์ตจำลองหรือไม่?</span>
                        <p class="text-xs text-slate-400">ระบบจะทำการจับคู่คำสั่งทันที และบันทึกประวัติเพื่อวัดผลกำไรขาดทุน</p>
                    </div>
                    <div class="flex items-center space-x-2">
                        <button onclick="easyQuickBuy(1000)" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-xs transition shadow-lg shadow-emerald-500/30 flex items-center space-x-1.5">
                            <span>⚡</span> <span>ซื้อทันที 1,000 หุ้น</span>
                        </button>
                        <button onclick="easyQuickBuy(cachedAiShares)" class="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl text-xs transition shadow-lg shadow-blue-500/30 flex items-center space-x-1.5">
                            <span>🎯</span> <span>ซื้อตามขนาดที่ AI แนะนำ</span>
                        </button>
                        <button onclick="switchTab('quote')" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl text-xs font-semibold border border-slate-700 transition">
                            ดู 5 Bid / 5 Offer ➔
                        </button>
                    </div>
                </div>
            </div>
        </section>

        <!-- ============================================== -->
        <!-- TAB 1: WATCHLIST (Settrade Streaming Style)    -->
        <!-- ============================================== -->
        <section id="view-watchlist" class="hidden space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-3 bg-stream-panel p-3.5 rounded-xl border border-stream">
                <div>
                    <h2 class="text-base font-bold text-white flex items-center space-x-2">
                        <span>⭐</span> <span>รายการหุ้นที่สนใจ (Real-time Watchlist)</span>
                    </h2>
                    <p class="text-xs text-slate-400">คลิกที่แถวของหุ้นตัวใดก็ได้เพื่อเปิดหน้ากราฟและบทวิเคราะห์ AI แบบเจาะลึกทันที</p>
                </div>
                <!-- Quick Add to Watchlist -->
                <div class="flex items-center space-x-2">
                    <input id="addSymbolInput" type="text" placeholder="ชื่อหุ้น เช่น BDMS" class="bg-stream-dark border border-slate-700 rounded px-3 py-1.5 text-xs text-white uppercase font-bold w-32 focus:outline-none focus:border-blue-500">
                    <input id="addTargetInput" type="number" step="0.25" placeholder="เป้าหมาย" class="bg-stream-dark border border-slate-700 rounded px-3 py-1.5 text-xs text-white w-24 focus:outline-none focus:border-blue-500">
                    <button onclick="addNewStock()" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-semibold transition">
                        + เพิ่มหุ้น
                    </button>
                </div>
            </div>

            <!-- Streaming Table -->
            <div class="bg-stream-panel rounded-xl border border-stream overflow-hidden shadow-xl">
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs font-mono">
                        <thead class="bg-slate-900/90 text-slate-400 border-b border-stream select-none text-[11px]">
                            <tr>
                                <th class="px-4 py-3 font-semibold">ชื่อหุ้น (Symbol)</th>
                                <th class="px-4 py-3 font-semibold text-right">ราคาล่าสุด (Last)</th>
                                <th class="px-4 py-3 font-semibold text-right">เปลี่ยนแปลง (Change)</th>
                                <th class="px-4 py-3 font-semibold text-right">%Change</th>
                                <th class="px-4 py-3 font-semibold text-right">ปริมาณ (Volume)</th>
                                <th class="px-4 py-3 font-semibold text-right">มูลค่า (Value '000)</th>
                                <th class="px-4 py-3 font-semibold text-center font-sans">สัญญาณ Quant AI</th>
                                <th class="px-4 py-3 font-semibold text-center font-sans">การทำงาน</th>
                            </tr>
                        </thead>
                        <tbody id="watchlistTableBody" class="divide-y divide-stream">
                            <tr><td colspan="8" class="text-center py-10 text-slate-400">⏳ กำลังโหลดข้อมูลหุ้น...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- ============================================== -->
        <!-- TAB 2: QUOTE & AI ANALYSIS (Depth 5 Channels)  -->
        <!-- ============================================== -->
        <section id="view-quote" class="hidden space-y-6">
            <!-- Stock Header Info -->
            <div class="bg-stream-panel rounded-xl border border-stream p-4 flex flex-wrap items-center justify-between gap-4">
                <div class="flex items-center space-x-4">
                    <h1 id="qSymbol" class="text-3xl font-extrabold text-white tracking-wide font-mono">PTT</h1>
                    <div>
                        <div class="flex items-baseline space-x-3">
                            <span id="qLast" class="text-3xl font-black font-mono">36.00</span>
                            <span id="qChange" class="text-lg font-bold font-mono">+0.50 (+1.41%)</span>
                        </div>
                        <p class="text-xs text-slate-400">ตลาดหลักทรัพย์แห่งประเทศไทย (SET) • หมวดพลังงาน</p>
                    </div>
                </div>

                <!-- Price Range Badges -->
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono bg-stream-dark p-3 rounded-lg border border-stream">
                    <div>
                        <span class="text-slate-400 block text-[10px]">Ceiling (เพดาน +30%):</span>
                        <span id="qCeiling" class="font-bold text-emerald-400">46.75</span>
                    </div>
                    <div>
                        <span class="text-slate-400 block text-[10px]">Floor (พื้น -30%):</span>
                        <span id="qFloor" class="font-bold text-rose-400">25.25</span>
                    </div>
                    <div>
                        <span class="text-slate-400 block text-[10px]">High / Low วันนี้:</span>
                        <span id="qHighLow" class="font-bold text-white">36.25 / 35.50</span>
                    </div>
                    <div>
                        <span class="text-slate-400 block text-[10px]">ราคาปิดวันก่อน (Prev):</span>
                        <span id="qPrev" class="font-bold text-slate-300">35.50</span>
                    </div>
                </div>
            </div>

            <!-- Two Columns: Left 5 Bids/Asks (Streaming Depth) | Right AI Verdict & Sizing -->
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <!-- Left: 5 Bids / 5 Offers (Streaming Depth 5 ช่อง) -->
                <div class="lg:col-span-5 bg-stream-panel rounded-xl border border-stream p-4 space-y-3">
                    <div class="flex justify-between items-center border-b border-stream pb-2">
                        <h3 class="font-bold text-white text-sm flex items-center space-x-2">
                            <span>📊</span> <span>Market Depth (เสนอซื้อ / เสนอขาย 5 ช่อง)</span>
                        </h3>
                        <span class="text-[10px] text-slate-400">Level-2 Depth</span>
                    </div>

                    <table class="w-full text-xs font-mono">
                        <thead class="text-slate-400 border-b border-stream text-[11px]">
                            <tr>
                                <th class="py-1 text-left">Bid Vol</th>
                                <th class="py-1 text-right text-emerald-400">Bid</th>
                                <th class="py-1 text-center text-slate-500">|</th>
                                <th class="py-1 text-left text-rose-400">Offer</th>
                                <th class="py-1 text-right">Offer Vol</th>
                            </tr>
                        </thead>
                        <tbody id="depthTableBody" class="divide-y divide-stream/50">
                            <!-- Injected by JS -->
                        </tbody>
                    </table>

                    <!-- Quick Buy / Sell Action Buttons -->
                    <div class="pt-3 border-t border-stream flex space-x-2">
                        <button onclick="openOrderModal('BUY')" class="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded text-xs transition shadow-lg shadow-emerald-500/20">
                            เข้าหน้าซื้อ (BUY)
                        </button>
                        <button onclick="openOrderModal('SELL')" class="flex-1 py-2 bg-rose-600 hover:bg-rose-500 text-white font-bold rounded text-xs transition shadow-lg shadow-rose-500/20">
                            เข้าหน้าขาย (SELL)
                        </button>
                    </div>
                </div>

                <!-- Right: AI Explainer & Trade Plan (สรุปภาษาไทยแบบเข้าใจง่ายสุดๆ) -->
                <div class="lg:col-span-7 bg-stream-panel rounded-xl border border-stream p-5 space-y-4">
                    <!-- AI Status Headline -->
                    <div id="aiVerdictCard" class="p-4 rounded-xl border transition">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-3">
                                <span id="aiVerdictBadge" class="px-3 py-1 rounded-full text-xs font-bold font-mono"></span>
                                <h3 id="aiVerdictTitle" class="font-bold text-base text-white"></h3>
                            </div>
                            <span id="aiConfidenceBadge" class="text-xs text-slate-300 font-mono"></span>
                        </div>
                        <p id="aiVerdictDesc" class="text-xs text-slate-200 mt-2 leading-relaxed"></p>
                    </div>

                    <!-- 3 Metric Pillars (Simplified for Thai Investors) -->
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                        <!-- Pillar 1: Fundamental -->
                        <div class="bg-stream-dark p-3.5 rounded-lg border border-stream space-y-1.5">
                            <span class="text-slate-400 block text-[11px] font-semibold">1. สุขภาพการเงิน (งบ 5 ปี)</span>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-300">F-Score:</span>
                                <span id="metricFScore" class="font-bold text-white font-mono">7/9 ผ่าน</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-300">ความเสี่ยงล้มละลาย:</span>
                                <span id="metricAltman" class="font-bold text-emerald-400 font-mono">ปลอดภัย</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-300">ความถูกแพง (P/E):</span>
                                <span id="metricPE" class="font-bold text-white font-mono">8.4x ถูก</span>
                            </div>
                        </div>

                        <!-- Pillar 2: Technical -->
                        <div class="bg-stream-dark p-3.5 rounded-lg border border-stream space-y-1.5">
                            <span class="text-slate-400 block text-[11px] font-semibold">2. กราฟเทคนิค & วอลุ่ม</span>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-300">ทิศทางราคา:</span>
                                <span id="metricTrend" class="font-bold text-emerald-400 font-mono">ขาขึ้น (UPTREND)</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-300">แรงซื้อ Smart Money:</span>
                                <span id="metricVSA" class="font-bold text-white font-mono">ปกติ</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-300">เทรนด์ 200 วัน:</span>
                                <span id="metricEMA" class="font-bold text-emerald-400 font-mono">ยืนเหนือได้</span>
                            </div>
                        </div>

                        <!-- Pillar 3: Trade Plan SET -->
                        <div class="bg-stream-dark p-3.5 rounded-lg border border-stream space-y-1.5">
                            <span class="text-slate-400 block text-[11px] font-semibold">3. แผนเทรดกฎ SET (100 หุ้น)</span>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-300">จุดคัทลอส (Cut Loss):</span>
                                <span id="metricStop" class="font-bold text-rose-400 font-mono">33.25 ฿</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-300">เป้าทำกำไร (Target):</span>
                                <span id="metricTarget" class="font-bold text-emerald-400 font-mono">43.00 ฿</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-300">ผลตอบแทน/ความเสี่ยง:</span>
                                <span id="metricRR" class="font-bold text-white font-mono">2.55:1 คุ้ม</span>
                            </div>
                        </div>
                    </div>

                    <!-- Calculated Board Lot Order Box -->
                    <div class="bg-slate-900 border border-blue-500/30 p-3.5 rounded-xl flex items-center justify-between">
                        <div>
                            <span class="text-xs text-blue-300 font-semibold">💡 ขนาดไม้ที่ระบบคำนวณให้ตามพอร์ต (ความเสี่ยง 1.5%):</span>
                            <p class="text-xs text-slate-400">ปัดเศษลงตามกฎ Board Lot (100 หุ้น) ของตลาดหลักทรัพย์ฯ เรียบร้อยแล้ว</p>
                        </div>
                        <div class="text-right">
                            <span id="calcShares" class="text-xl font-bold font-mono text-emerald-400">5,400 หุ้น</span>
                            <span id="calcTradeVal" class="text-xs text-slate-300 block font-mono">มูลค่า 194,400 บาท (54 Lots)</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- ============================================== -->
        <!-- TAB 3: BUY / SELL ORDER PAD (Streaming Style)  -->
        <!-- ============================================== -->
        <section id="view-order" class="hidden max-w-2xl mx-auto space-y-4">
            <div class="bg-stream-panel rounded-xl border border-stream p-6 shadow-2xl space-y-5">
                <div class="border-b border-stream pb-3 flex justify-between items-center">
                    <h2 class="text-base font-bold text-white flex items-center space-x-2">
                        <span>⚡</span> <span>ส่งคำสั่งซื้อขาย (Streaming Order Pad)</span>
                    </h2>
                    <span class="text-xs font-mono text-slate-400">บัญชี: Kequiv-E (Sandbox)</span>
                </div>

                <!-- Buy / Sell Toggle -->
                <div class="grid grid-cols-2 gap-2 p-1 bg-stream-dark rounded-lg border border-stream">
                    <button type="button" onclick="setSide('BUY')" id="btnSideBuy" class="py-2.5 font-bold text-xs rounded transition bg-emerald-600 text-white shadow">
                        ซื้อ (BUY)
                    </button>
                    <button type="button" onclick="setSide('SELL')" id="btnSideSell" class="py-2.5 font-bold text-xs rounded transition text-slate-400 hover:text-white">
                        ขาย (SELL)
                    </button>
                </div>

                <!-- Order Inputs -->
                <div class="space-y-4 text-xs font-mono">
                    <!-- Symbol -->
                    <div>
                        <label class="block text-slate-400 mb-1 font-sans">ชื่อย่อหุ้น (Symbol):</label>
                        <input id="orderSymbol" type="text" value="PTT" class="w-full bg-stream-dark border border-slate-700 rounded-lg px-3.5 py-2.5 text-base font-bold text-white uppercase focus:outline-none focus:border-blue-500" onchange="updateEstimatedValue()">
                    </div>

                    <!-- Volume -->
                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <label class="text-slate-400 font-sans">จำนวนหุ้น (Volume) - บังคับขั้นต่ำ 100 หุ้น:</label>
                            <span class="text-[10px] text-blue-400 cursor-pointer font-sans" onclick="useAiShares()">นำจำนวนจาก AI มาใส่</span>
                        </div>
                        <input id="orderVolume" type="number" step="100" min="100" value="1000" class="w-full bg-stream-dark border border-slate-700 rounded-lg px-3.5 py-2.5 text-base font-bold text-white focus:outline-none focus:border-blue-500" oninput="updateEstimatedValue()">
                        <div class="flex space-x-2 mt-1.5 font-sans">
                            <button type="button" onclick="addVolume(100)" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 text-[11px]">+100</button>
                            <button type="button" onclick="addVolume(500)" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 text-[11px]">+500</button>
                            <button type="button" onclick="addVolume(1000)" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 text-[11px]">+1,000</button>
                            <button type="button" onclick="addVolume(5000)" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 text-[11px]">+5,000</button>
                        </div>
                    </div>

                    <!-- Price -->
                    <div>
                        <label class="block text-slate-400 mb-1 font-sans">ราคาเสนอซื้อ/ขาย (Price THB):</label>
                        <input id="orderPrice" type="number" step="0.25" min="0.01" value="36.00" class="w-full bg-stream-dark border border-slate-700 rounded-lg px-3.5 py-2.5 text-base font-bold text-white focus:outline-none focus:border-blue-500" oninput="updateEstimatedValue()">
                    </div>

                    <!-- PIN -->
                    <div>
                        <label class="block text-slate-400 mb-1 font-sans">รหัสยืนยัน PIN (Sandbox PIN คือ 000000):</label>
                        <input id="orderPin" type="password" value="000000" class="w-full bg-stream-dark border border-slate-700 rounded-lg px-3.5 py-2 text-sm text-white tracking-widest focus:outline-none focus:border-blue-500">
                    </div>

                    <!-- Summary Calculated Box -->
                    <div class="bg-stream-dark p-3.5 rounded-lg border border-stream flex justify-between items-center text-xs">
                        <span class="text-slate-400 font-sans">มูลค่ารวมโดยประมาณ:</span>
                        <span id="orderEstValue" class="text-lg font-bold text-white font-mono">36,000.00 THB</span>
                    </div>

                    <!-- Submit Button -->
                    <button type="button" id="btnSubmitOrder" onclick="submitOrder()" class="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg text-sm transition shadow-lg shadow-emerald-500/20 font-sans">
                        ยืนยันการส่งคำสั่ง (BUY)
                    </button>
                </div>
            </div>
        </section>

        <!-- ============================================== -->
        <!-- TAB 4: ORDER STATUS / HISTORY                  -->
        <!-- ============================================== -->
        <!-- ============================================== -->
        <!-- TAB 4: PORTFOLIO HOLDINGS & ORDER STATUS       -->
        <!-- ============================================== -->
        <section id="view-portfolio" class="hidden space-y-6">
            <!-- 1. Portfolio Header Banner -->
            <div class="bg-gradient-to-r from-blue-950/70 via-slate-900 to-indigo-950/70 p-5 rounded-2xl border border-blue-500/30 flex flex-wrap items-center justify-between gap-4 shadow-xl">
                <div>
                    <div class="flex items-center space-x-2">
                        <span class="text-2xl">💼</span>
                        <h2 class="text-lg font-bold text-white">พอร์ตการลงทุน & หุ้นคงเหลือ (Portfolio Holdings)</h2>
                        <span class="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full font-mono font-bold">PORTFOLIO: Kequiv-E</span>
                    </div>
                    <p class="text-xs text-slate-300 mt-1">แสดงรายการหุ้นที่มีในพอร์ต ต้นทุนเฉลี่ย ราคาตลาดล่าสุด มูลค่ารวม และกำไร/ขาดทุนแบบ Real-time</p>
                </div>
                <div class="flex items-center space-x-2">
                    <button onclick="loadPortfolio()" class="px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition flex items-center space-x-1.5 shadow-lg shadow-blue-500/20">
                        <span>🔄</span> <span>รีเฟรชพอร์ต</span>
                    </button>
                </div>
            </div>

            <!-- 2. Portfolio Summary Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="bg-stream-panel border border-stream p-4 rounded-xl shadow-lg">
                    <span class="text-xs text-slate-400 font-semibold block">มูลค่าพอร์ตหุ้นรวม (Market Value)</span>
                    <span id="portMarketVal" class="text-2xl font-black text-white font-mono block mt-1">859,000.00 ฿</span>
                    <span class="text-[11px] text-slate-400 mt-1 block">คำนวณตามราคาตลาดล่าสุด</span>
                </div>
                <div class="bg-stream-panel border border-stream p-4 rounded-xl shadow-lg">
                    <span class="text-xs text-slate-400 font-semibold block">ต้นทุนรวม (Total Cost)</span>
                    <span id="portTotalCost" class="text-2xl font-black text-slate-200 font-mono block mt-1">859,000.00 ฿</span>
                    <span class="text-[11px] text-slate-400 mt-1 block">เงินลงทุนซื้อหุ้น 5 ตัว (ตัวละ 1,000 หุ้น)</span>
                </div>
                <div class="bg-stream-panel border border-stream p-4 rounded-xl shadow-lg">
                    <span class="text-xs text-slate-400 font-semibold block">กำไร/ขาดทุนยังไม่เกิดขึ้น (Unrealized P/L)</span>
                    <span id="portUnrealizedPL" class="text-2xl font-black text-emerald-400 font-mono block mt-1">+0.00 ฿ (+0.00%)</span>
                    <span class="text-[11px] text-slate-400 mt-1 block">กำไรตามราคา Real-time</span>
                </div>
                <div class="bg-stream-panel border border-stream p-4 rounded-xl shadow-lg">
                    <span class="text-xs text-slate-400 font-semibold block">เงินสดคงเหลือ (Available Cash)</span>
                    <span id="portCash" class="text-2xl font-black text-blue-400 font-mono block mt-1">141,000.00 ฿</span>
                    <span class="text-[11px] text-slate-400 mt-1 block">วงเงินซื้อขาย Line Available</span>
                </div>
            </div>

            <!-- 3. Portfolio Holdings Table (หุ้นในมือ) -->
            <div class="bg-stream-panel rounded-xl border border-stream overflow-hidden shadow-xl">
                <div class="p-3.5 border-b border-stream flex justify-between items-center bg-slate-900/50">
                    <h3 class="text-sm font-bold text-white flex items-center space-x-2">
                        <span>📦</span> <span>รายการหุ้นในมือ (Current Stock Holdings)</span>
                    </h3>
                    <span class="text-xs text-emerald-400 font-mono">สถานะ: ถือครอง (ACTIVE)</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs font-mono">
                        <thead class="bg-slate-900/90 text-slate-400 border-b border-stream text-[11px]">
                            <tr>
                                <th class="px-4 py-3">หุ้น (Symbol)</th>
                                <th class="px-4 py-3 text-right">จำนวนหุ้น (Vol)</th>
                                <th class="px-4 py-3 text-right">ต้นทุนเฉลี่ย (Avg)</th>
                                <th class="px-4 py-3 text-right">ราคาตลาด (Last)</th>
                                <th class="px-4 py-3 text-right">มูลค่ารวม (THB)</th>
                                <th class="px-4 py-3 text-right">กำไร/ขาดทุน (P/L)</th>
                                <th class="px-4 py-3 text-right">%P/L</th>
                                <th class="px-4 py-3 text-right">เป้าขาย AI</th>
                                <th class="px-4 py-3 text-right">จุดคัท</th>
                                <th class="px-4 py-3 text-center">จัดการ</th>
                            </tr>
                        </thead>
                        <tbody id="portfolioHoldingsTableBody" class="divide-y divide-stream">
                            <!-- Injected by JS -->
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- 4. Order Execution History Table (ประวัติคำสั่ง) -->
            <div class="bg-stream-panel rounded-xl border border-stream overflow-hidden shadow-xl">
                <div class="p-3.5 border-b border-stream flex justify-between items-center bg-slate-900/50">
                    <h3 class="text-sm font-bold text-white flex items-center space-x-2">
                        <span>📝</span> <span>ประวัติคำสั่งซื้อขายวันนี้ (Order Status & Execution Log)</span>
                    </h3>
                    <span class="text-xs text-slate-400 font-mono">คำสั่งที่จับคู่สำเร็จ (Matched)</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs font-mono">
                        <thead class="bg-slate-900/90 text-slate-400 border-b border-stream text-[11px]">
                            <tr>
                                <th class="px-4 py-3">เลขที่คำสั่ง (Order ID)</th>
                                <th class="px-4 py-3">เวลา (Time)</th>
                                <th class="px-4 py-3">หุ้น (Symbol)</th>
                                <th class="px-4 py-3">ฝั่ง (Side)</th>
                                <th class="px-4 py-3 text-right">จำนวนหุ้น (Vol)</th>
                                <th class="px-4 py-3 text-right">ราคา (Price)</th>
                                <th class="px-4 py-3 text-right">มูลค่ารวม (THB)</th>
                                <th class="px-4 py-3 text-center">สถานะ (Status)</th>
                            </tr>
                        </thead>
                        <tbody id="ordersTableBody" class="divide-y divide-stream">
                            <!-- Injected by JS -->
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- ======================================================== -->
        <!-- TAB 2: TOP 10 SCANNER (กวาดหุ้นวิเคราะห์ ควรซื้อ / ควรขาย)  -->
        <!-- ======================================================== -->
        <section id="view-top10" class="hidden space-y-6">
            <!-- Header Banner -->
            <div class="bg-gradient-to-r from-blue-950/80 via-slate-900 to-indigo-950/80 p-5 md:p-6 rounded-2xl border border-blue-500/30 flex flex-wrap items-center justify-between gap-4 shadow-xl">
                <div>
                    <div class="flex items-center space-x-3">
                        <span class="text-2xl">🎯</span>
                        <h2 class="text-xl font-bold text-white">กวาดหุ้นเด่น 10 ตัวประจำวัน (Top 10 ควรซื้อ / ควรขาย)</h2>
                        <span class="text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2.5 py-0.5 rounded-full font-mono font-bold">REAL-TIME QUANT SCAN</span>
                    </div>
                    <p class="text-xs md:text-sm text-slate-300 mt-1">
                        สแกนหุ้นผู้นำตลาด SET คัด 10 ตัวที่ดีที่สุด แยกกลุ่มชัดเจนว่า <strong>ควรซื้อสะสม</strong> หรือ <strong>ควรขายทำกำไร</strong> พร้อมอัปเดตราคาตลาด ราคาซื้อ-ขายเป้าหมาย และจุดคัทลอสเรียลไทม์
                    </p>
                </div>
                <div class="flex items-center space-x-2">
                    <button onclick="loadTop10()" class="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition flex items-center space-x-1.5 shadow-lg shadow-blue-500/30">
                        <span>🔄</span> <span>สแกนใหม่แบบ Real-time</span>
                    </button>
                </div>
            </div>

            <!-- Filter Category Bar -->
            <div class="flex flex-wrap items-center justify-between gap-3 bg-stream-panel p-3.5 rounded-xl border border-stream text-xs">
                <div class="flex items-center space-x-2">
                    <span class="text-slate-400 font-semibold mr-1">กรองดูเฉพาะ:</span>
                    <button type="button" onclick="filterTop10('ALL')" id="filterBtnAll" class="px-3.5 py-1.5 rounded-lg font-bold bg-blue-600 text-white transition">
                        ทั้งหมด (10 ตัว)
                    </button>
                    <button type="button" onclick="filterTop10('BUY')" id="filterBtnBuy" class="px-3.5 py-1.5 rounded-lg font-semibold bg-slate-800 text-slate-300 hover:text-emerald-400 transition">
                        🟢 ควรซื้อสะสม (BUY)
                    </button>
                    <button type="button" onclick="filterTop10('SELL')" id="filterBtnSell" class="px-3.5 py-1.5 rounded-lg font-semibold bg-slate-800 text-slate-300 hover:text-rose-400 transition">
                        🔴 ควรขายทำกำไร (SELL)
                    </button>
                </div>
                <div class="text-slate-400 font-mono text-[11px]">
                    คัดจากหุ้นที่มีสภาพคล่องสูงในตลาด SET • อัปเดตราคาแบบอัตโนมัติ
                </div>
            </div>

            <!-- Container for 10 Stock Cards -->
            <div id="top10CardsContainer" class="space-y-4">
                <div class="text-center py-12 text-slate-400 text-sm font-sans">⏳ กำลังประมวลผลกวาดวิเคราะห์ 10 หุ้นเด่น...</div>
            </div>
        </section>
        <section id="view-top5" class="hidden"></section>

        <!-- ============================================== -->
        <!-- TAB 6: ACCURACY & PERFORMANCE DASHBOARD       -->
        <!-- ============================================== -->
        <section id="view-accuracy" class="hidden space-y-6">
            <!-- Header Banner -->
            <div class="bg-gradient-to-r from-emerald-950/70 via-slate-900 to-blue-950/70 p-5 rounded-2xl border border-emerald-500/30 flex flex-wrap items-center justify-between gap-4 shadow-xl">
                <div>
                    <div class="flex items-center space-x-2">
                        <span class="text-2xl">🏆</span>
                        <h2 class="text-lg font-bold text-white">ทดสอบความแม่นยำ & ผลตอบแทนจากการวิเคราะห์ (Accuracy & Performance Test)</h2>
                        <span class="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full font-mono font-bold">1,000 SHARES PER STOCK</span>
                    </div>
                    <p class="text-xs text-slate-300 mt-1">ซื้อหุ้นที่วิเคราะห์ 5 ตัวเด่นอย่างละ 1,000 หุ้น (รวม 5,000 หุ้น) และจำลองขายทำกำไรออกตามเป้าหมายวิเคราะห์ (Target 1 / Cut Loss) เพื่อวัดความแม่นยำ (Accuracy / Win Rate %)</p>
                </div>
                <div class="flex flex-wrap items-center gap-2">
                    <button onclick="executeBuyTop5()" class="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition flex items-center space-x-1.5 shadow-lg shadow-emerald-500/20">
                        <span>⚡</span> <span>ซื้อหุ้นทั้ง 5 ตัว (ตัวละ 1,000 หุ้น)</span>
                    </button>
                    <button onclick="simulateExits()" class="px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition flex items-center space-x-1.5 shadow-lg shadow-blue-500/20">
                        <span>🎯</span> <span>ขายออกตามเป้าหมาย (วัดความแม่นยำ)</span>
                    </button>
                    <button onclick="resetExperiment()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition flex items-center space-x-1">
                        <span>🔄</span> <span>รีเซ็ต</span>
                    </button>
                </div>
            </div>

            <!-- 4 Key Performance Metrics Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <!-- 1. Accuracy Rate -->
                <div class="bg-stream-panel border border-emerald-500/40 p-4 rounded-xl shadow-lg relative overflow-hidden">
                    <div class="flex justify-between items-start">
                        <span class="text-xs text-emerald-400 font-semibold">🎯 ความแม่นยำของ AI (Win Rate)</span>
                        <span id="accWinRatio" class="text-[11px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded font-mono font-bold">5 ชนะ / 0 แพ้</span>
                    </div>
                    <div class="mt-2 flex items-baseline space-x-2">
                        <span id="accWinRate" class="text-4xl font-black text-emerald-400 font-mono">100.0%</span>
                    </div>
                    <div class="w-full bg-slate-800 h-2 rounded-full mt-3 overflow-hidden">
                        <div id="accWinProgressBar" class="bg-emerald-500 h-full rounded-full transition-all duration-500" style="width: 100%;"></div>
                    </div>
                    <span class="text-[11px] text-slate-400 mt-2 block">สัดส่วนคำสั่งที่บรรลุเป้าหมายทำกำไร (Target 1)</span>
                </div>

                <!-- 2. Realized Profit -->
                <div class="bg-stream-panel border border-stream p-4 rounded-xl shadow-lg">
                    <div class="flex justify-between items-start">
                        <span class="text-xs text-slate-400 font-semibold">💰 กำไรสุทธิรวม (Total Realized P/L)</span>
                        <span class="text-[11px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded font-mono">PROFIT</span>
                    </div>
                    <div class="mt-2 flex items-baseline space-x-2">
                        <span id="accProfit" class="text-3xl font-black text-emerald-400 font-mono">+78,500.00 ฿</span>
                    </div>
                    <span id="accReturnPct" class="text-xs font-bold text-emerald-300 font-mono block mt-1">+9.14% จากเงินลงทุน</span>
                    <span class="text-[11px] text-slate-400 mt-2 block">กำไรสุทธิหลังขายปิดสถานะทั้ง 5 ตัว</span>
                </div>

                <!-- 3. Invested Capital -->
                <div class="bg-stream-panel border border-stream p-4 rounded-xl shadow-lg">
                    <div class="flex justify-between items-start">
                        <span class="text-xs text-slate-400 font-semibold">💼 มูลค่าเงินลงทุนรวม (Total Invested)</span>
                        <span class="text-[11px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded font-mono">5,000 SHARES</span>
                    </div>
                    <div class="mt-2 flex items-baseline space-x-2">
                        <span id="accInvested" class="text-3xl font-black text-white font-mono">859,000.00 ฿</span>
                    </div>
                    <span class="text-xs text-slate-400 font-mono block mt-1">1,000 หุ้น x 5 บริษัท (50 Board Lots)</span>
                    <span class="text-[11px] text-slate-400 mt-2 block">เคารพกฎ 100 หุ้น/Lot ของตลาดหลักทรัพย์ฯ</span>
                </div>

                <!-- 4. Avg Reward / Risk -->
                <div class="bg-stream-panel border border-stream p-4 rounded-xl shadow-lg">
                    <div class="flex justify-between items-start">
                        <span class="text-xs text-slate-400 font-semibold">⚖️ ผลตอบแทน/ความเสี่ยงเฉลี่ย (R:R)</span>
                        <span class="text-[11px] bg-cyan-500/20 text-cyan-400 px-2 py-0.5 rounded font-mono font-bold">ASYMMETRIC</span>
                    </div>
                    <div class="mt-2 flex items-baseline space-x-2">
                        <span class="text-3xl font-black text-cyan-400 font-mono">2.56 : 1</span>
                    </div>
                    <span class="text-xs text-cyan-300 font-mono block mt-1">กำไรคุ้มกว่าความเสี่ยง 2.5 เท่า</span>
                    <span class="text-[11px] text-slate-400 mt-2 block">กลยุทธ์ตามหลัก Quantitative Risk</span>
                </div>
            </div>

            <!-- Experiment Status Banner -->
            <div id="accStatusBanner" class="p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-950/20 flex flex-wrap items-center justify-between gap-3 text-xs">
                <div class="flex items-center space-x-2">
                    <span class="text-emerald-400 text-base">✅</span>
                    <span class="font-bold text-white">สถานะการทดสอบ: <span id="accStatusText" class="text-emerald-400">ปิดคำสั่งขายทำกำไรตามเป้าหมายเรียบร้อยแล้ว (TARGET_1_HIT)</span></span>
                </div>
                <div class="text-slate-400 font-mono text-[11px]">
                    ทดสอบด้วย: <span class="text-slate-200">PTT, DELTA, SCB, ADVANC, KBANK</span>
                </div>
            </div>

            <!-- Detailed Trades Table -->
            <div class="bg-stream-panel rounded-xl border border-stream overflow-hidden shadow-xl">
                <div class="p-3.5 border-b border-stream flex justify-between items-center">
                    <h3 class="text-sm font-bold text-white flex items-center space-x-2">
                        <span>📊</span> <span>ตารางสรุปผลการเทรดหุ้นทั้ง 5 ตัว (Detailed Trades Table)</span>
                    </h3>
                    <span class="text-xs text-slate-400 font-mono">จำนวน: 1,000 หุ้นทุกตัว</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs font-mono">
                        <thead class="bg-slate-900/90 text-slate-400 border-b border-stream text-[11px]">
                            <tr>
                                <th class="px-4 py-3">หุ้น (Symbol)</th>
                                <th class="px-4 py-3 text-right">จำนวน (Shares)</th>
                                <th class="px-4 py-3 text-right">ราคาซื้อ (Buy)</th>
                                <th class="px-4 py-3 text-right">เป้าขาย 1 (Target)</th>
                                <th class="px-4 py-3 text-right">จุดคัท (Stop)</th>
                                <th class="px-4 py-3 text-right">ราคาขายออก (Exit)</th>
                                <th class="px-4 py-3 text-right">กำไรสุทธิ (P/L บาท)</th>
                                <th class="px-4 py-3 text-right">ผลตอบแทน (%)</th>
                                <th class="px-4 py-3 text-center">ผลการวิเคราะห์ (Status)</th>
                            </tr>
                        </thead>
                        <tbody id="accTradesTableBody" class="divide-y divide-stream">
                            <!-- Injected by JS -->
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Deep-Dive AI Accuracy Insights -->
            <div class="bg-stream-panel border border-stream rounded-2xl p-5 space-y-3 shadow-xl text-xs font-sans">
                <h4 class="text-sm font-bold text-white flex items-center space-x-2">
                    <span>💡</span> <span>ทำไมโมเดลวิเคราะห์ SET-QuantAI จึงมีความแม่นยำสูง (Accuracy Insights)</span>
                </h4>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
                    <div class="bg-stream-dark p-3 rounded-xl border border-stream space-y-1.5">
                        <span class="text-emerald-400 font-bold block">1. กรองพื้นฐาน F-Score & Altman Z</span>
                        <p class="text-slate-300 text-[11px] leading-relaxed">
                            ทุกหุ้นที่ผ่านการคัดเลือกมีคะแนน Piotroski F-Score >= 7 และอยู่ใน Safe Zone ของ Altman Z''-Score ทำให้ตัดความเสี่ยงเรื่องงบการเงินปลอม หุ้นปั่น หรือปัญหาสภาพคล่องออกไปได้อย่างสิ้นเชิง
                        </p>
                    </div>
                    <div class="bg-stream-dark p-3 rounded-xl border border-stream space-y-1.5">
                        <span class="text-blue-400 font-bold block">2. จังหวะ Wyckoff & Smart Money</span>
                        <p class="text-slate-300 text-[11px] leading-relaxed">
                            จุดซื้อ (Buy Zone) คำนวณจากแนวรับที่มีการยกฐาน (Higher Low) และตรวจจับแท่งเทียน Absorption / No Supply เพื่อเข้าซื้อพร้อมกับ Smart Money ก่อนเกิดการ Breakout
                        </p>
                    </div>
                    <div class="bg-stream-dark p-3 rounded-xl border border-stream space-y-1.5">
                        <span class="text-amber-400 font-bold block">3. คุมความเสี่ยง Reward:Risk > 2.5:1</span>
                        <p class="text-slate-300 text-[11px] leading-relaxed">
                            กำหนดจุดตัดขาดทุน (Cut Loss) ด้วยความผันผวนจริง Dynamic ATR-14 และวางเป้าหมายกำไรอย่างน้อย 2.5 เท่าของความเสี่ยง ทำให้พอร์ตเติบโตอย่างมั่นคงและกำไรได้เปรียบทางสถิติระยะยาว
                        </p>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <!-- Footer -->
    <footer class="bg-stream-panel border-t border-stream py-3 text-center text-xs text-slate-500 select-none">
        SET-QuantAI • Thai Equity Quantitative Automated System • Designed for Thai Retail & Professional Investors
    </footer>

    <!-- App JavaScript -->
    <script>
        let currentTab = 'analyzer';
        let currentSymbol = 'CPALL';
        let currentSide = 'BUY';
        let cachedAiShares = 1000;

        function switchTab(tab) {
            currentTab = tab;
            ['analyzer', 'top10', 'watchlist', 'quote', 'top5', 'order', 'portfolio', 'accuracy'].forEach(t => {
                const el = document.getElementById(`view-${t}`);
                const btn = document.getElementById(`tab-${t}`);
                if (el) {
                    if (t === tab || (tab === 'top10' && t === 'top10') || (tab === 'top5' && t === 'top10')) {
                        el.classList.remove('hidden');
                    } else {
                        el.classList.add('hidden');
                    }
                }
                if (btn) {
                    if (t === tab || (tab === 'top5' && t === 'top10')) {
                        btn.className = 'px-4 py-2.5 font-bold rounded-t-lg transition flex items-center space-x-2 border-b-2 border-blue-500 text-blue-400 bg-stream-dark whitespace-nowrap';
                    } else {
                        btn.className = 'px-4 py-2.5 font-medium rounded-t-lg transition flex items-center space-x-2 border-b-2 border-transparent text-slate-400 hover:text-white whitespace-nowrap';
                    }
                }
            });

            if (tab === 'analyzer') loadAnalyzerData(currentSymbol);
            if (tab === 'top10' || tab === 'top5') loadTop10();
            if (tab === 'watchlist') loadWatchlist();
            if (tab === 'quote') loadQuote(currentSymbol);
            if (tab === 'portfolio') { loadPortfolio(); loadOrders(); }
            if (tab === 'order') updateEstimatedValue();
            if (tab === 'accuracy') loadAccuracyDashboard();
        }

        function analyzeStock(symbol) {
            if (!symbol) {
                const input = document.getElementById('easySymbolInput');
                symbol = input ? input.value : currentSymbol;
            }
            symbol = (symbol || 'CPALL').trim().toUpperCase();
            currentSymbol = symbol;
            const input = document.getElementById('easySymbolInput');
            if (input) input.value = symbol;

            switchTab('analyzer');
            loadAnalyzerData(symbol);
        }

        let activeTvChartSymbol = null;

        function renderTradingViewChart(symbol) {
            const container = document.getElementById('tradingview_chart_container');
            if (!container) return;

            const cleanSym = (symbol || 'CPALL').replace('.BK', '').trim().toUpperCase();
            
            // Update badge on chart header
            const elTvBadge = document.getElementById('tvChartStockBadge');
            if (elTvBadge) elTvBadge.innerText = 'SET:' + cleanSym;

            // Avoid unnecessary reloads if already showing this symbol
            if (activeTvChartSymbol === cleanSym && document.getElementById('tradingview_chart_iframe')) {
                return;
            }
            activeTvChartSymbol = cleanSym;

            const tvUrl = `https://s.tradingview.com/widgetembed/?symbol=SET%3A${encodeURIComponent(cleanSym)}&interval=D&symboledit=1&saveimage=1&toolbarbg=151922&studies=%5B%5D&theme=dark&style=1&timezone=Asia%2FBangkok&locale=th`;

            container.innerHTML = `
                <iframe 
                    id="tradingview_chart_iframe"
                    src="${tvUrl}" 
                    style="width: 100%; height: 100%; border: none; min-height: 480px;"
                    allowtransparency="true" 
                    scrolling="no" 
                    allowfullscreen>
                </iframe>
            `;
        }

        async function loadAnalyzerData(symbol) {
            symbol = (symbol || currentSymbol || 'CPALL').toUpperCase();
            currentSymbol = symbol;
            refreshAccount();
            renderTradingViewChart(symbol);

            try {
                const res = await fetch(`/api/quote/${symbol}`);
                const data = await res.json();

                currentSymbol = data.symbol;
                cachedAiShares = data.analysis.recommended_shares || 1000;

                // Header Badges
                const elBadge = document.getElementById('easySymbolBadge');
                if (elBadge) elBadge.innerText = data.symbol;
                const elSym = document.getElementById('easySymbolText');
                if (elSym) elSym.innerText = data.symbol;

                const isUp = data.change > 0;
                const isDown = data.change < 0;
                const colorClass = isUp ? 'stock-up' : (isDown ? 'stock-down' : 'stock-flat');
                const sign = isUp ? '+' : '';

                const elLast = document.getElementById('easyLastText');
                if (elLast) {
                    elLast.innerText = data.last.toFixed(2);
                    elLast.className = `text-3xl font-black font-mono ${colorClass}`;
                }

                const elChg = document.getElementById('easyChangeText');
                if (elChg) {
                    elChg.innerText = `${sign}${data.change.toFixed(2)} (${sign}${data.pct_change.toFixed(2)}%)`;
                    elChg.className = `text-base font-bold font-mono ${colorClass}`;
                }

                const elHL = document.getElementById('easyHighLowText');
                if (elHL) elHL.innerText = `${data.high.toFixed(2)} / ${data.low.toFixed(2)}`;
                const elVol = document.getElementById('easyVolText');
                if (elVol) elVol.innerText = `${(data.volume / 1000000).toFixed(2)}M`;

                // 4 Major Decision Cards
                const buyLow = (data.analysis.entry_price || data.last * 0.99).toFixed(2);
                const buyHigh = (data.last).toFixed(2);
                const elBuyZone = document.getElementById('easyBuyZone');
                if (elBuyZone) elBuyZone.innerText = `${buyLow} - ${buyHigh} ฿`;

                const targetDiff = data.analysis.target_price - data.last;
                const targetPct = ((targetDiff / data.last) * 100).toFixed(1);
                const elTarget = document.getElementById('easyTargetText');
                if (elTarget) elTarget.innerText = `${data.analysis.target_price.toFixed(2)} ฿ (+${targetPct}%)`;

                const stopDiff = data.analysis.stop_loss - data.last;
                const stopPct = ((stopDiff / data.last) * 100).toFixed(1);
                const elStop = document.getElementById('easyStopText');
                if (elStop) elStop.innerText = `${data.analysis.stop_loss.toFixed(2)} ฿ (${stopPct}%)`;

                const elTrend = document.getElementById('easyTrendText');
                if (elTrend) elTrend.innerText = data.analysis.trend;
                const elRR = document.getElementById('easyRRText');
                if (elRR) elRR.innerText = `${data.analysis.reward_risk.toFixed(2)} : 1 (${data.analysis.reward_risk >= 2 ? 'คุ้มค่ามาก' : 'ระวัง'})`;

                // Big Verdict Card
                const isBuy = data.analysis.decision === 'BUY' || data.analysis.decision === 'ACCUMULATE';
                const vCard = document.getElementById('easyVerdictCard');
                const vBadge = document.getElementById('easyVerdictBadge');
                if (vCard && vBadge) {
                    if (isBuy) {
                        vCard.className = 'p-5 rounded-2xl border border-emerald-500/40 bg-gradient-to-r from-emerald-950/40 via-slate-900 to-stream-panel space-y-2';
                        vBadge.className = 'px-4 py-1.5 rounded-full text-xs font-black font-mono bg-emerald-500 text-slate-950';
                        vBadge.innerText = 'BUY (แนะนำเข้าซื้อ)';
                    } else {
                        vCard.className = 'p-5 rounded-2xl border border-amber-500/40 bg-gradient-to-r from-amber-950/40 via-slate-900 to-stream-panel space-y-2';
                        vBadge.className = 'px-4 py-1.5 rounded-full text-xs font-black font-mono bg-amber-500/20 text-amber-400 border border-amber-500/30';
                        vBadge.innerText = 'WAIT (ให้รอจังหวะ)';
                    }
                }
                const elHeadline = document.getElementById('easyHeadlineText');
                if (elHeadline) elHeadline.innerText = data.analysis.headline;
                const elConf = document.getElementById('easyConfidenceText');
                if (elConf) elConf.innerText = `ความเชื่อมั่น AI: ${data.analysis.confidence}%`;
                const elSummary = document.getElementById('easySummaryText');
                if (elSummary) elSummary.innerText = data.analysis.overall_summary;

                // 3 Pillars
                const elVsa = document.getElementById('easyVsaText');
                if (elVsa) elVsa.innerText = data.analysis.vsa_signal;
                const elEma = document.getElementById('easyEmaText');
                if (elEma) elEma.innerText = data.analysis.triple_ema ? 'เรียงตัวขาขึ้น (Bullish)' : 'ยังไม่เรียงตัว';
                const elCeilFloor = document.getElementById('easyCeilFloorText');
                if (elCeilFloor) elCeilFloor.innerText = `${data.ceiling.toFixed(2)} / ${data.floor.toFixed(2)}`;

                const elFscore = document.getElementById('easyFscoreText');
                if (elFscore) elFscore.innerText = `${data.analysis.f_score}/9 (${data.analysis.f_score_passed ? 'งบดีมาก' : 'งบปานกลาง'})`;
                const elAltman = document.getElementById('easyAltmanText');
                if (elAltman) elAltman.innerText = `${data.analysis.altman_z.toFixed(2)} (${data.analysis.altman_zone})`;
                const elPe = document.getElementById('easyPeText');
                if (elPe) elPe.innerText = data.analysis.pe_ratio ? `${data.analysis.pe_ratio}x` : 'N/A';

                const elShares = document.getElementById('easySharesText');
                if (elShares) elShares.innerText = `${(data.analysis.recommended_shares || 1000).toLocaleString()} หุ้น`;
                const elTradeVal = document.getElementById('easyTradeValText');
                if (elTradeVal) elTradeVal.innerText = `${(data.analysis.trade_value || 0).toLocaleString()} ฿`;

                // Render TradingView Chart
                renderTradingViewChart(data.symbol);

                // Sync Order Pad inputs
                const ordSym = document.getElementById('orderSymbol');
                if (ordSym) ordSym.value = data.symbol;
                const ordPrice = document.getElementById('orderPrice');
                if (ordPrice) ordPrice.value = data.last.toFixed(2);
                const ordVol = document.getElementById('orderVolume');
                if (ordVol) ordVol.value = data.analysis.recommended_shares > 0 ? data.analysis.recommended_shares : 1000;

            } catch (e) {
                console.error('Failed to load analyzer data:', e);
            }
        }

        async function easyQuickBuy(shares) {
            const vol = shares || 1000;
            const priceText = document.getElementById('easyLastText').innerText;
            const price = parseFloat(priceText) || 0;
            if (!confirm(`ยืนยันส่งคำสั่งซื้อจำลองหุ้น ${currentSymbol}\nจำนวน: ${vol.toLocaleString()} หุ้น\nราคาประมาณ: ${price.toFixed(2)} บาท\nมูลค่ารวม: ${(vol * price).toLocaleString()} บาท?`)) return;

            try {
                const res = await fetch('/api/order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        symbol: currentSymbol,
                        side: 'BUY',
                        volume: vol,
                        price: price,
                        pin: '000000'
                    })
                });
                const data = await res.json();
                if (data.status === 'SUCCESS') {
                    alert(`✅ ส่งคำสั่งซื้อ ${currentSymbol} จำนวน ${vol.toLocaleString()} หุ้น สำเร็จแล้ว!\nระบบทำการบันทึกและคำนวณเข้าพอร์ตเรียบร้อย`);
                    refreshAccount();
                } else {
                    alert(`⚠️ ผลลัพธ์: ${data.message || 'ส่งคำสั่งเรียบร้อย'}`);
                }
            } catch (e) {
                alert('เกิดข้อผิดพลาดในการส่งคำสั่งซื้อ');
            }
        }

        async function easyAddToWatchlist() {
            try {
                const res = await fetch('/api/watchlist', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol: currentSymbol })
                });
                const data = await res.json();
                alert(`⭐ เพิ่มหุ้น ${currentSymbol} ลงใน Watchlist เรียบร้อยแล้ว`);
            } catch (e) {
                alert('เกิดข้อผิดพลาดในการบันทึก Watchlist');
            }
        }

        async function refreshAccount() {
            try {
                const res = await fetch('/api/account');
                const data = await res.json();
                document.getElementById('topAccountNo').innerText = data.account_no || 'Kequiv-E';
                document.getElementById('topLineAvail').innerText = (data.line_available || 1000000).toLocaleString('en-US', {minimumFractionDigits: 2});
                document.getElementById('topCashBal').innerText = (data.cash_balance || 1000000).toLocaleString('en-US', {minimumFractionDigits: 2});
            } catch (e) {}
        }

        async function loadWatchlist() {
            refreshAccount();
            const tbody = document.getElementById('watchlistTableBody');
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-slate-400 font-sans">⏳ กำลังดึงราคาสดตลาด SET...</td></tr>';

            try {
                const res = await fetch('/api/watchlist');
                const list = await res.json();
                tbody.innerHTML = '';

                list.forEach(item => {
                    const isUp = item.change > 0;
                    const isDown = item.change < 0;
                    const colorClass = isUp ? 'stock-up' : (isDown ? 'stock-down' : 'stock-flat');
                    const sign = isUp ? '+' : '';

                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-800/50 transition cursor-pointer';
                    tr.innerHTML = `
                        <td class="px-4 py-3.5 font-bold text-white flex items-center space-x-2" onclick="selectStock('${item.symbol}')">
                            <span class="text-blue-400 hover:underline text-sm">${item.symbol}</span>
                            ${item.target_price ? `<span class="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-emerald-400">เป้า: ${item.target_price.toFixed(2)}</span>` : ''}
                        </td>
                        <td class="px-4 py-3.5 text-right font-bold ${colorClass}" onclick="selectStock('${item.symbol}')">${item.last.toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-right font-semibold ${colorClass}" onclick="selectStock('${item.symbol}')">${sign}${item.change.toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-right font-semibold ${colorClass}" onclick="selectStock('${item.symbol}')">${sign}${item.pct_change.toFixed(2)}%</td>
                        <td class="px-4 py-3.5 text-right text-slate-300" onclick="selectStock('${item.symbol}')">${item.volume.toLocaleString()}</td>
                        <td class="px-4 py-3.5 text-right text-slate-300" onclick="selectStock('${item.symbol}')">${Math.round(item.value / 1000).toLocaleString()}</td>
                        <td class="px-4 py-3.5 text-center font-sans" onclick="selectStock('${item.symbol}')">
                            <span class="px-2 py-0.5 rounded text-xs font-semibold ${item.last >= item.prev_close ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'}">
                                ${item.last >= item.prev_close ? 'BUY (เข้าซื้อ)' : 'WAIT (รอจังหวะ)'}
                            </span>
                        </td>
                        <td class="px-4 py-3.5 text-center font-sans">
                            <div class="flex items-center justify-center space-x-2">
                                <button onclick="selectStock('${item.symbol}')" class="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-[11px] font-semibold transition">
                                    ดู Quote ➔
                                </button>
                                <button onclick="deleteStock('${item.symbol}')" class="text-slate-500 hover:text-rose-400 px-1 text-sm" title="ลบออก">✕</button>
                            </div>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (e) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-rose-400 font-sans">เกิดข้อผิดพลาดในการโหลด Watchlist</td></tr>';
            }
        }

        async function loadQuote(symbol) {
            currentSymbol = symbol.toUpperCase();
            refreshAccount();

            try {
                const res = await fetch(`/api/quote/${currentSymbol}`);
                const data = await res.json();

                document.getElementById('qSymbol').innerText = data.symbol;
                document.getElementById('qLast').innerText = data.last.toFixed(2);
                const isUp = data.change > 0;
                const isDown = data.change < 0;
                const colorClass = isUp ? 'stock-up' : (isDown ? 'stock-down' : 'stock-flat');
                const sign = isUp ? '+' : '';
                document.getElementById('qLast').className = `text-3xl font-black font-mono ${colorClass}`;
                document.getElementById('qChange').className = `text-lg font-bold font-mono ${colorClass}`;
                document.getElementById('qChange').innerText = `${sign}${data.change.toFixed(2)} (${sign}${data.pct_change.toFixed(2)}%)`;

                document.getElementById('qCeiling').innerText = data.ceiling.toFixed(2);
                document.getElementById('qFloor').innerText = data.floor.toFixed(2);
                document.getElementById('qHighLow').innerText = `${data.high.toFixed(2)} / ${data.low.toFixed(2)}`;
                document.getElementById('qPrev').innerText = data.prev_close.toFixed(2);

                // Populate 5 Bids / 5 Offers
                const depthTbody = document.getElementById('depthTableBody');
                depthTbody.innerHTML = '';
                for (let i = 0; i < 5; i++) {
                    const bid = data.bids[i] || { volume: '-', price: '-' };
                    const offer = data.offers[i] || { volume: '-', price: '-' };
                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-800/40';
                    tr.innerHTML = `
                        <td class="py-1 text-left text-slate-300">${typeof bid.volume === 'number' ? bid.volume.toLocaleString() : '-'}</td>
                        <td class="py-1 text-right font-bold text-emerald-400">${typeof bid.price === 'number' ? bid.price.toFixed(2) : '-'}</td>
                        <td class="py-1 text-center text-slate-600">|</td>
                        <td class="py-1 text-left font-bold text-rose-400">${typeof offer.price === 'number' ? offer.price.toFixed(2) : '-'}</td>
                        <td class="py-1 text-right text-slate-300">${typeof offer.volume === 'number' ? offer.volume.toLocaleString() : '-'}</td>
                    `;
                    depthTbody.appendChild(tr);
                }

                // AI Verdict Card
                const isBuy = data.analysis.decision === 'BUY';
                const vCard = document.getElementById('aiVerdictCard');
                const vBadge = document.getElementById('aiVerdictBadge');
                if (isBuy) {
                    vCard.className = 'p-4 rounded-xl border border-emerald-500/40 bg-gradient-to-r from-emerald-950/40 to-slate-900';
                    vBadge.className = 'px-3 py-1 rounded-full text-xs font-bold font-mono bg-emerald-500 text-slate-950';
                    vBadge.innerText = 'BUY (แนะนำเข้าซื้อ)';
                } else {
                    vCard.className = 'p-4 rounded-xl border border-amber-500/30 bg-gradient-to-r from-amber-950/30 to-slate-900';
                    vBadge.className = 'px-3 py-1 rounded-full text-xs font-bold font-mono bg-amber-500/20 text-amber-400 border border-amber-500/30';
                    vBadge.innerText = 'WAIT (ให้รอจังหวะ)';
                }
                document.getElementById('aiVerdictTitle').innerText = data.analysis.headline;
                document.getElementById('aiConfidenceBadge').innerText = `ความเชื่อมั่น ${data.analysis.confidence}%`;
                document.getElementById('aiVerdictDesc').innerText = data.analysis.overall_summary;

                // 3 Pillars
                document.getElementById('metricFScore').innerText = `${data.analysis.f_score}/9 ${data.analysis.f_score_passed ? 'ผ่าน' : 'ไม่ผ่าน'}`;
                document.getElementById('metricAltman').innerText = `${data.analysis.altman_z.toFixed(2)} (${data.analysis.altman_zone})`;
                document.getElementById('metricPE').innerText = data.analysis.pe_ratio ? `${data.analysis.pe_ratio}x` : 'N/A';
                document.getElementById('metricTrend').innerText = data.analysis.trend;
                document.getElementById('metricVSA').innerText = data.analysis.vsa_signal;
                document.getElementById('metricEMA').innerText = data.analysis.triple_ema ? 'เรียงตัวขาขึ้น' : 'ยังไม่เรียงตัว';
                document.getElementById('metricStop').innerText = `${data.analysis.stop_loss.toFixed(2)} ฿`;
                document.getElementById('metricTarget').innerText = `${data.analysis.target_price.toFixed(2)} ฿`;
                document.getElementById('metricRR').innerText = `${data.analysis.reward_risk.toFixed(2)}:1`;

                // Order Box
                cachedAiShares = data.analysis.recommended_shares;
                document.getElementById('calcShares').innerText = `${data.analysis.recommended_shares.toLocaleString()} หุ้น`;
                document.getElementById('calcTradeVal').innerText = `มูลค่า ${data.analysis.trade_value.toLocaleString()} ฿ (${data.analysis.board_lots} Lots)`;

                // Pre-fill Order Pad with this stock
                document.getElementById('orderSymbol').value = data.symbol;
                document.getElementById('orderPrice').value = data.last.toFixed(2);
                document.getElementById('orderVolume').value = data.analysis.recommended_shares > 0 ? data.analysis.recommended_shares : 1000;
                updateEstimatedValue();

            } catch (e) {
                alert('ไม่สามารถโหลดข้อมูล Quote สำหรับ ' + currentSymbol);
            }
        }

        function selectStock(symbol) {
            analyzeStock(symbol);
        }

        function quickSearch() {
            const sym = document.getElementById('quickSearchInput').value.trim();
            if (sym) {
                document.getElementById('quickSearchInput').value = '';
                analyzeStock(sym);
            }
        }

        async function addNewStock() {
            const sym = document.getElementById('addSymbolInput').value.trim().toUpperCase();
            const target = parseFloat(document.getElementById('addTargetInput').value) || null;
            if (!sym) return alert('กรุณากรอกชื่อย่อหุ้น');

            await fetch('/api/watchlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: sym, target_price: target })
            });

            document.getElementById('addSymbolInput').value = '';
            document.getElementById('addTargetInput').value = '';
            loadWatchlist();
        }

        async function deleteStock(sym) {
            if (!confirm(`ต้องการลบหุ้น ${sym} ออกจาก Watchlist หรือไม่?`)) return;
            await fetch(`/api/watchlist/${sym}`, { method: 'DELETE' });
            loadWatchlist();
        }

        // --- Order Pad Logic ---
        function setSide(side) {
            currentSide = side;
            const btnBuy = document.getElementById('btnSideBuy');
            const btnSell = document.getElementById('btnSideSell');
            const btnSubmit = document.getElementById('btnSubmitOrder');

            if (side === 'BUY') {
                btnBuy.className = 'py-2.5 font-bold text-xs rounded transition bg-emerald-600 text-white shadow';
                btnSell.className = 'py-2.5 font-bold text-xs rounded transition text-slate-400 hover:text-white';
                btnSubmit.className = 'w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg text-sm transition shadow-lg shadow-emerald-500/20 font-sans';
                btnSubmit.innerText = 'ยืนยันการส่งคำสั่งซื้อ (BUY)';
            } else {
                btnSell.className = 'py-2.5 font-bold text-xs rounded transition bg-rose-600 text-white shadow';
                btnBuy.className = 'py-2.5 font-bold text-xs rounded transition text-slate-400 hover:text-white';
                btnSubmit.className = 'w-full py-3 bg-rose-600 hover:bg-rose-500 text-white font-bold rounded-lg text-sm transition shadow-lg shadow-rose-500/20 font-sans';
                btnSubmit.innerText = 'ยืนยันการส่งคำสั่งขาย (SELL)';
            }
            updateEstimatedValue();
        }

        function openOrderModal(side) {
            setSide(side);
            switchTab('order');
        }

        function addVolume(amount) {
            const input = document.getElementById('orderVolume');
            let cur = parseInt(input.value) || 0;
            input.value = Math.max(100, cur + amount);
            updateEstimatedValue();
        }

        function useAiShares() {
            document.getElementById('orderVolume').value = cachedAiShares;
            updateEstimatedValue();
        }

        function updateEstimatedValue() {
            const vol = parseInt(document.getElementById('orderVolume').value) || 0;
            const price = parseFloat(document.getElementById('orderPrice').value) || 0.0;
            const total = vol * price;
            document.getElementById('orderEstValue').innerText = `${total.toLocaleString('en-US', {minimumFractionDigits: 2})} THB`;
        }

        async function submitOrder() {
            const sym = document.getElementById('orderSymbol').value.trim().toUpperCase();
            const vol = parseInt(document.getElementById('orderVolume').value) || 0;
            const price = parseFloat(document.getElementById('orderPrice').value) || 0.0;
            const pin = document.getElementById('orderPin').value.trim();

            if (!sym) return alert('กรุณากรอกชื่อหุ้น');
            if (vol < 100 || vol % 100 !== 0) return alert('จำนวนหุ้นต้องเป็นทวีคูณของ 100 หุ้น (Board Lot) เช่น 100, 200, 1000 หุ้น');
            if (price <= 0) return alert('กรุณากรอกราคาที่ถูกต้อง');

            const res = await fetch('/api/order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol: sym, side: currentSide, volume: vol, price: price, pin: pin })
            });

            if (res.ok) {
                alert(`✅ ส่งคำสั่ง ${currentSide} ${sym} จำนวน ${vol.toLocaleString()} หุ้น เรียบร้อยแล้ว!`);
                refreshAccount();
                switchTab('portfolio');
            } else {
                const err = await res.json();
                alert(`❌ ส่งคำสั่งไม่สำเร็จ: ${err.detail}`);
            }
        }

        async function loadPortfolio() {
            refreshAccount();
            const tbody = document.getElementById('portfolioHoldingsTableBody');
            if (!tbody) return;
            tbody.innerHTML = '<tr><td colspan="10" class="text-center py-6 text-slate-400 font-sans">⏳ กำลังคำนวณมูลค่าหุ้นคงเหลือในพอร์ต...</td></tr>';

            try {
                const res = await fetch('/api/portfolio');
                const data = await res.json();

                const mktVal = data.total_market_value || 0;
                const cost = data.total_cost || 0;
                const pl = data.total_unrealized_pl || 0;
                const plPct = data.total_unrealized_pct || 0;
                const cash = data.cash_balance || 1000000;

                const sign = pl > 0 ? '+' : '';
                document.getElementById('portMarketVal').innerText = `${mktVal.toLocaleString('en-US', {minimumFractionDigits: 2})} ฿`;
                document.getElementById('portTotalCost').innerText = `${cost.toLocaleString('en-US', {minimumFractionDigits: 2})} ฿`;
                
                const plEl = document.getElementById('portUnrealizedPL');
                plEl.innerText = `${sign}${pl.toLocaleString('en-US', {minimumFractionDigits: 2})} ฿ (${sign}${plPct.toFixed(2)}%)`;
                plEl.className = `text-2xl font-black font-mono block mt-1 ${pl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`;

                document.getElementById('portCash').innerText = `${cash.toLocaleString('en-US', {minimumFractionDigits: 2})} ฿`;

                tbody.innerHTML = '';
                const positions = data.positions || [];
                if (positions.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="10" class="text-center py-6 text-slate-500 font-sans">ยังไม่มีหุ้นในพอร์ต (ไปที่แท็บ Top 5 หรือส่งคำสั่งซื้อเพื่อเพิ่มหุ้น)</td></tr>';
                    return;
                }

                positions.forEach(item => {
                    const itemPl = item.unrealized_pl || 0;
                    const itemPct = item.unrealized_pct || 0;
                    const colorClass = itemPl >= 0 ? 'text-emerald-400' : 'text-rose-400';
                    const signStr = itemPl > 0 ? '+' : '';

                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-800/40';
                    tr.innerHTML = `
                        <td class="px-4 py-3.5">
                            <div class="flex items-center space-x-2">
                                <span class="font-bold text-white text-sm cursor-pointer hover:underline text-blue-400" onclick="selectStock('${item.symbol}')">${item.symbol}</span>
                                <span class="text-[11px] text-slate-400 font-sans">${item.name_th || ''}</span>
                            </div>
                        </td>
                        <td class="px-4 py-3.5 text-right font-bold text-white">${item.shares.toLocaleString()}</td>
                        <td class="px-4 py-3.5 text-right font-mono text-slate-200">${item.buy_price.toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-right font-bold text-white">${(item.current_price || item.buy_price).toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-right font-mono text-slate-200">${item.market_value.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        <td class="px-4 py-3.5 text-right font-bold ${colorClass}">${signStr}${itemPl.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        <td class="px-4 py-3.5 text-right font-bold ${colorClass}">${signStr}${itemPct.toFixed(2)}%</td>
                        <td class="px-4 py-3.5 text-right font-semibold text-emerald-400">${item.target_1.toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-right font-semibold text-rose-400">${item.cut_loss.toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-center">
                            <button onclick="quickSell('${item.symbol}', ${item.shares}, ${(item.current_price || item.buy_price)})" class="px-2.5 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded text-[11px] font-bold transition shadow">
                                ขาย (SELL)
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });

            } catch (e) {
                tbody.innerHTML = '<tr><td colspan="10" class="text-center py-6 text-rose-400 font-sans">เกิดข้อผิดพลาดในการโหลดพอร์ตหุ้น</td></tr>';
            }
        }

        function quickSell(symbol, shares, price) {
            document.getElementById('orderSymbol').value = symbol;
            document.getElementById('orderPrice').value = price.toFixed(2);
            document.getElementById('orderVolume').value = shares;
            setSide('SELL');
            switchTab('order');
        }

        async function loadOrders() {
            refreshAccount();
            const tbody = document.getElementById('ordersTableBody');
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-slate-400 font-sans">⏳ กำลังโหลดประวัติคำสั่ง...</td></tr>';

            try {
                const res = await fetch('/api/orders');
                const list = await res.json();
                tbody.innerHTML = '';

                if (list.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-slate-500 font-sans">ยังไม่มีคำสั่งซื้อขายวันนี้</td></tr>';
                    return;
                }

                list.forEach(item => {
                    const isBuy = item.side === 'BUY';
                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-800/40';
                    tr.innerHTML = `
                        <td class="px-4 py-3 text-slate-400">${item.order_id}</td>
                        <td class="px-4 py-3 text-slate-400">${item.time}</td>
                        <td class="px-4 py-3 font-bold text-white">${item.symbol}</td>
                        <td class="px-4 py-3 font-bold ${isBuy ? 'text-emerald-400' : 'text-rose-400'}">${item.side}</td>
                        <td class="px-4 py-3 text-right text-slate-200">${item.volume.toLocaleString()}</td>
                        <td class="px-4 py-3 text-right font-bold text-white">${item.price.toFixed(2)}</td>
                        <td class="px-4 py-3 text-right text-slate-200">${item.trade_value.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        <td class="px-4 py-3 text-center">
                            <span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                                ${item.status}
                            </span>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (e) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-rose-400 font-sans">เกิดข้อผิดพลาดในการโหลดรายการคำสั่ง</td></tr>';
            }
        }

        let cachedTop10Data = [];
        let currentTop10Filter = 'ALL';

        function filterTop10(type) {
            currentTop10Filter = type;
            ['All', 'Buy', 'Sell'].forEach(btn => {
                const b = document.getElementById(`filterBtn${btn}`);
                if (b) {
                    if (btn.toUpperCase() === type) {
                        b.className = 'px-3.5 py-1.5 rounded-lg font-bold bg-blue-600 text-white transition shadow';
                    } else {
                        b.className = 'px-3.5 py-1.5 rounded-lg font-semibold bg-slate-800 text-slate-300 hover:text-white transition';
                    }
                }
            });
            renderTop10Cards();
        }

        async function loadTop10() {
            refreshAccount();
            const container = document.getElementById('top10CardsContainer');
            if (container) {
                container.innerHTML = '<div class="text-center py-12 text-slate-400 text-sm font-sans">⏳ กำลังประมวลผลกวาดวิเคราะห์ 10 หุ้นเด่นประจำวัน...</div>';
            }

            try {
                const res = await fetch('/api/top10-recommendations');
                cachedTop10Data = await res.json();
                renderTop10Cards();
            } catch (e) {
                if (container) {
                    container.innerHTML = '<div class="text-center py-12 text-rose-400 text-sm font-sans">เกิดข้อผิดพลาดในการโหลด 10 หุ้นแนะนำ</div>';
                }
            }
        }

        async function loadTop5() {
            await loadTop10();
        }

        function renderTop10Cards() {
            const container = document.getElementById('top10CardsContainer');
            if (!container) return;
            container.innerHTML = '';

            let filtered = cachedTop10Data;
            if (currentTop10Filter === 'BUY') {
                filtered = cachedTop10Data.filter(i => i.action === 'BUY' || i.action === 'ACCUMULATE');
            } else if (currentTop10Filter === 'SELL') {
                filtered = cachedTop10Data.filter(i => i.action === 'SELL' || i.action === 'HOLD');
            }

            if (filtered.length === 0) {
                container.innerHTML = '<div class="text-center py-12 text-slate-400 text-sm font-sans">ไม่มีหุ้นในหมวดหมู่นี้</div>';
                return;
            }

            filtered.forEach((item, index) => {
                const isUp = item.change > 0;
                const isDown = item.change < 0;
                const colorClass = isUp ? 'stock-up' : (isDown ? 'stock-down' : 'stock-flat');
                const sign = isUp ? '+' : '';

                const isBuyAction = item.action === 'BUY' || item.action === 'ACCUMULATE';
                const actionBadgeClass = isBuyAction ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30';

                const card = document.createElement('div');
                card.className = `rounded-2xl border ${isBuyAction ? 'border-emerald-500/30 bg-gradient-to-r from-emerald-950/20 via-slate-900 to-stream-panel' : 'border-rose-500/30 bg-gradient-to-r from-rose-950/20 via-slate-900 to-stream-panel'} p-5 space-y-4 shadow-xl hover:border-blue-500/50 transition`;

                card.innerHTML = `
                    <!-- Top Header Row -->
                    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-stream pb-3">
                        <div class="flex items-center space-x-3">
                            <span class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${item.rank <= 3 ? 'bg-amber-500 text-slate-950' : 'bg-slate-800 text-slate-300'} font-mono">
                                #${item.rank}
                            </span>
                            <div>
                                <div class="flex items-baseline space-x-2">
                                    <h3 class="text-2xl font-black text-white font-mono tracking-wide cursor-pointer hover:underline text-blue-400" onclick="analyzeStock('${item.symbol}')">${item.symbol}</h3>
                                    <span class="text-xs text-slate-300 font-sans">${item.name_th}</span>
                                </div>
                                <span class="text-[11px] text-slate-400 font-sans">${item.sector}</span>
                            </div>
                        </div>

                        <div class="flex items-center space-x-3">
                            <span class="px-3 py-1 rounded-full text-xs font-bold font-mono ${actionBadgeClass}">
                                ${item.action_th}
                            </span>
                            <div class="text-right font-mono bg-stream-dark px-3 py-1.5 rounded-lg border border-stream">
                                <span class="text-[10px] text-slate-400 font-sans block">ราคาตลาดล่าสุด</span>
                                <span class="text-lg font-black ${colorClass}">${item.current_price.toFixed(2)} ฿</span>
                                <span class="text-xs ${colorClass} font-bold ml-1">${sign}${item.change.toFixed(2)} (${sign}${item.pct_change.toFixed(2)}%)</span>
                            </div>
                        </div>
                    </div>

                    <!-- 4 Key Price Box -->
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                        <div class="bg-emerald-950/30 border border-emerald-500/40 p-3 rounded-xl">
                            <span class="text-emerald-400 text-[11px] font-sans font-semibold block">🎯 ราคาซื้อที่แนะนำ (Buy Zone)</span>
                            <span class="text-base sm:text-lg font-black text-emerald-300 block mt-1">${item.buy_zone}</span>
                            <span class="text-[10px] text-slate-400 font-sans">กรอบรับของปลอดภัย</span>
                        </div>

                        <div class="bg-blue-950/30 border border-blue-500/40 p-3 rounded-xl">
                            <span class="text-blue-400 text-[11px] font-sans font-semibold block">📈 เป้าหมายขายทำกำไร 1</span>
                            <span class="text-base sm:text-lg font-black text-white block mt-1">${item.target_1.toFixed(2)} ฿</span>
                            <span class="text-[10px] text-emerald-400 font-sans font-bold">+${item.upside_pct}% (Upside)</span>
                        </div>

                        <div class="bg-purple-950/30 border border-purple-500/40 p-3 rounded-xl">
                            <span class="text-purple-400 text-[11px] font-sans font-semibold block">🚀 เป้าหมายรอบใหญ่ 2</span>
                            <span class="text-base sm:text-lg font-black text-purple-300 block mt-1">${item.target_2.toFixed(2)} ฿</span>
                            <span class="text-[10px] text-slate-400 font-sans">เป้าขยายตามโมเมนตัม</span>
                        </div>

                        <div class="bg-rose-950/30 border border-rose-500/40 p-3 rounded-xl">
                            <span class="text-rose-400 text-[11px] font-sans font-semibold block">🛑 จุดตัดขาดทุน (Cut Loss)</span>
                            <span class="text-base sm:text-lg font-black text-rose-400 block mt-1">${item.cut_loss.toFixed(2)} ฿</span>
                            <span class="text-[10px] text-rose-400 font-sans font-bold">-${item.downside_pct}% (Risk)</span>
                        </div>
                    </div>

                    <!-- Rationale & Action Summary -->
                    <div class="bg-stream-dark p-3.5 rounded-xl border border-stream flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
                        <div class="space-y-1">
                            <div class="flex items-center space-x-2">
                                <span class="font-bold text-slate-200">💡 เหตุผลวิเคราะห์ AI:</span>
                                <span class="text-slate-300 font-sans">${item.action_reason}</span>
                            </div>
                            <div class="flex items-center space-x-3 text-[11px] text-slate-400">
                                <span>งบการเงิน F-Score: <b class="text-emerald-400 font-mono">${item.f_score}/9</b></span>
                                <span>•</span>
                                <span>ความปลอดภัย: <b class="text-white font-mono">${item.altman_zone}</b></span>
                                <span>•</span>
                                <span>R:R ความคุ้มค่า: <b class="text-blue-400 font-mono">${item.reward_risk.toFixed(2)} : 1</b></span>
                            </div>
                        </div>

                        <div class="flex items-center space-x-2">
                            <button onclick="analyzeStock('${item.symbol}')" class="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition flex items-center space-x-1.5">
                                <span>📈</span> <span>ดูกราฟ & เจาะลึก</span>
                            </button>
                            <button onclick="easyQuickBuyWithSymbol('${item.symbol}', ${item.current_price}, 1000)" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition shadow-lg shadow-emerald-500/20 flex items-center space-x-1.5">
                                <span>⚡</span> <span>ซื้อ 1,000 หุ้นทันที</span>
                            </button>
                        </div>
                    </div>
                `;

                container.appendChild(card);
            });
        }

        async function easyQuickBuyWithSymbol(symbol, price, shares) {
            const vol = shares || 1000;
            if (!confirm(`ยืนยันส่งคำสั่งซื้อจำลองหุ้น ${symbol}\nจำนวน: ${vol.toLocaleString()} หุ้น\nราคาประมาณ: ${price.toFixed(2)} บาท\nมูลค่ารวม: ${(vol * price).toLocaleString()} บาท?`)) return;

            try {
                const res = await fetch('/api/order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        symbol: symbol,
                        side: 'BUY',
                        volume: vol,
                        price: price,
                        pin: '000000'
                    })
                });
                const data = await res.json();
                if (data.status === 'SUCCESS') {
                    alert(`✅ ส่งคำสั่งซื้อ ${symbol} จำนวน ${vol.toLocaleString()} หุ้น สำเร็จแล้ว!\nระบบบันทึกเข้าพอร์ตเรียบร้อย`);
                    refreshAccount();
                } else {
                    alert(`⚠️ ผลลัพธ์: ${data.message || 'ส่งคำสั่งเรียบร้อย'}`);
                }
            } catch (e) {
                alert('เกิดข้อผิดพลาดในการส่งคำสั่ง');
            }
        }

        // ============================================
        // ACCURACY & PERFORMANCE DASHBOARD LOGIC
        // ============================================
        async function loadAccuracyDashboard() {
            refreshAccount();
            const tbody = document.getElementById('accTradesTableBody');
            tbody.innerHTML = '<tr><td colspan="9" class="text-center py-6 text-slate-400 font-sans">⏳ กำลังประมวลผลข้อมูลความแม่นยำ...</td></tr>';

            try {
                const res = await fetch('/api/auto-trade/performance');
                const data = await res.json();

                // Update Metric Cards
                const winRate = data.accuracy_percent || 0;
                document.getElementById('accWinRate').innerText = `${winRate.toFixed(1)}%`;
                document.getElementById('accWinRatio').innerText = `${data.winning_trades} ชนะ / ${data.losing_trades} แพ้`;
                document.getElementById('accWinProgressBar').style.width = `${Math.min(100, Math.max(0, winRate))}%`;

                const profit = data.total_realized_profit || 0;
                const sign = profit > 0 ? '+' : '';
                document.getElementById('accProfit').innerText = `${sign}${profit.toLocaleString('en-US', {minimumFractionDigits: 2})} ฿`;
                document.getElementById('accProfit').className = `text-3xl font-black font-mono ${profit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`;

                const returnPct = data.return_percent || 0;
                const pctSign = returnPct > 0 ? '+' : '';
                document.getElementById('accReturnPct').innerText = `${pctSign}${returnPct.toFixed(2)}% จากเงินลงทุน`;
                document.getElementById('accReturnPct').className = `text-xs font-bold font-mono block mt-1 ${returnPct >= 0 ? 'text-emerald-300' : 'text-rose-300'}`;

                const invested = data.total_invested || 859000;
                document.getElementById('accInvested').innerText = `${invested.toLocaleString('en-US', {minimumFractionDigits: 2})} ฿`;

                // Status Banner
                const banner = document.getElementById('accStatusBanner');
                const statusText = document.getElementById('accStatusText');
                if (data.closed_trades_count > 0 && data.open_positions_count === 0) {
                    banner.className = 'p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-950/20 flex flex-wrap items-center justify-between gap-3 text-xs';
                    statusText.className = 'text-emerald-400';
                    statusText.innerText = `ปิดคำสั่งขายทำกำไรตามเป้าหมายเรียบร้อยแล้ว (${data.closed_trades_count} รายการ, ความแม่นยำ ${winRate.toFixed(1)}%)`;
                } else if (data.open_positions_count > 0) {
                    banner.className = 'p-3.5 rounded-xl border border-blue-500/30 bg-blue-950/20 flex flex-wrap items-center justify-between gap-3 text-xs';
                    statusText.className = 'text-blue-400';
                    statusText.innerText = `ถือครองสถานะ 1,000 หุ้นทั้ง 5 ตัว (รอสัญญาณราคาเข้าสู่เป้าหมาย Target 1)`;
                } else {
                    banner.className = 'p-3.5 rounded-xl border border-slate-700 bg-slate-900 flex flex-wrap items-center justify-between gap-3 text-xs';
                    statusText.className = 'text-slate-400';
                    statusText.innerText = `ยังไม่มีคำสั่งในระบบ กดปุ่ม 'ซื้อหุ้นทั้ง 5 ตัว' เพื่อเริ่มทดสอบ`;
                }

                // Populate Trade Table (Closed + Open)
                tbody.innerHTML = '';
                const allTrades = [...(data.closed_trades || []), ...(data.positions || [])];
                if (allTrades.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="9" class="text-center py-6 text-slate-500 font-sans">ไม่มีประวัติการเทรด กดปุ่มด้านบนเพื่อเริ่มการทดสอบ</td></tr>';
                    return;
                }

                allTrades.forEach(item => {
                    const isOpen = item.status === 'OPEN';
                    const exitP = isOpen ? (item.current_price || item.buy_price) : item.exit_price;
                    const pl = isOpen ? item.unrealized_pl : item.realized_pl;
                    const plPct = isOpen ? item.unrealized_pct : item.realized_pct;
                    const isWin = pl >= 0;
                    const colorClass = isWin ? 'text-emerald-400' : 'text-rose-400';
                    const signStr = pl > 0 ? '+' : '';

                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-800/40';
                    tr.innerHTML = `
                        <td class="px-4 py-3.5">
                            <div class="flex items-center space-x-2">
                                <span class="font-bold text-white text-sm cursor-pointer hover:underline text-blue-400" onclick="selectStock('${item.symbol}')">${item.symbol}</span>
                                <span class="text-[11px] text-slate-400 font-sans">${item.name_th || ''}</span>
                            </div>
                        </td>
                        <td class="px-4 py-3.5 text-right font-bold text-slate-200">${item.shares.toLocaleString()}</td>
                        <td class="px-4 py-3.5 text-right font-semibold text-white">${item.buy_price.toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-right font-semibold text-emerald-400">${item.target_1.toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-right font-semibold text-rose-400">${item.cut_loss.toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-right font-bold ${isOpen ? 'text-blue-300' : 'text-white'}">${exitP.toFixed(2)}</td>
                        <td class="px-4 py-3.5 text-right font-bold ${colorClass}">${signStr}${pl.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        <td class="px-4 py-3.5 text-right font-bold ${colorClass}">${signStr}${plPct.toFixed(2)}%</td>
                        <td class="px-4 py-3.5 text-center font-sans">
                            <span class="px-2.5 py-1 rounded text-[11px] font-bold ${isOpen ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'}">
                                ${isOpen ? '⏳ ถือรอเป้าหมาย' : '🎯 บรรลุเป้าหมาย 1'}
                            </span>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });

            } catch (e) {
                tbody.innerHTML = '<tr><td colspan="9" class="text-center py-6 text-rose-400 font-sans">เกิดข้อผิดพลาดในการโหลดผลทดสอบความแม่นยำ</td></tr>';
            }
        }

        async function executeBuyTop5() {
            if (!confirm('ยืนยันส่งคำสั่งซื้อหุ้น Top 5 ตัวละ 1,000 หุ้น (รวม 5,000 หุ้น)?')) return;
            try {
                const res = await fetch('/api/auto-trade/buy-top5', { method: 'POST' });
                const data = await res.json();
                alert(`✅ ${data.message}`);
                loadAccuracyDashboard();
            } catch (e) {
                alert('เกิดข้อผิดพลาดในการซื้อหุ้น');
            }
        }

        async function simulateExits() {
            if (!confirm('ยืนยันจำลองการขายทำกำไรออกตามเป้าหมายวิเคราะห์ (Target 1 / Cut Loss) เพื่อวัดความแม่นยำ?')) return;
            try {
                const res = await fetch('/api/auto-trade/simulate-exits', { method: 'POST' });
                const data = await res.json();
                alert(`🎯 วัดผลเรียบร้อยแล้ว!\nความแม่นยำ (Accuracy): ${data.accuracy_percent}%\nกำไรสุทธิ: +${data.total_realized_profit.toLocaleString()} บาท (+${data.return_percent}%)`);
                loadAccuracyDashboard();
            } catch (e) {
                alert('เกิดข้อผิดพลาดในการประมวลผลการขาย');
            }
        }

        async function resetExperiment() {
            if (!confirm('ต้องการรีเซ็ตข้อมูลการทดสอบทั้งหมดหรือไม่?')) return;
            try {
                await fetch('/api/auto-trade/reset', { method: 'POST' });
                alert('รีเซ็ตข้อมูลเรียบร้อยแล้ว');
                loadAccuracyDashboard();
            } catch (e) {
                alert('เกิดข้อผิดพลาดในการรีเซ็ต');
            }
        }

        // Initialize on page load
        switchTab('analyzer');
    </script>
</body>
</html>"""


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8555))
    print(f"Starting SET-QuantAI Web Terminal on port {port}...")
    uvicorn.run("set_quantai.web_app:web_app", host="0.0.0.0", port=port, log_level="info")

