"""SET-QuantAI Thai Command Line Interface (CLI)

Interactive, rich Thai terminal interface for:
- Analyzing focus stocks on demand
- Managing Watchlist & Custom Universe
- Scanning watchlist for confluence trade signals
- Inspecting SET compliance rules
"""

from typing import List, Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from set_quantai.core.pipeline import QuantAIPipeline, AnalysisReport
from set_quantai.core.compliance import SETCompliance
from set_quantai.core.models import MarketDirection
from set_quantai.core.top_picks import TopPicksEngine
from set_quantai.core.auto_trader import AutoTraderEngine

app = typer.Typer(
    help="ระบบวิเคราะห์หุ้นไทยเชิงปริมาณและสัญญาณเทรดอัตโนมัติ (SET-QuantAI)",
    no_args_is_help=True,
)
watchlist_app = typer.Typer(help="จัดการรายชื่อหุ้นที่สนใจ (Watchlist & Custom Focus List)")
app.add_typer(watchlist_app, name="watchlist")

console = Console()


def print_header():
    title = Text("📈 ระบบ SET-QuantAI: Quantitative Trading & AI Explainer สำหรับตลาดหุ้นไทย", style="bold cyan")
    console.print(Panel(title, box=box.ROUNDED, border_style="bright_blue"))


@app.command("analyze")
def analyze(
    symbol: str = typer.Argument(..., help="ชื่อย่อหุ้นไทยที่ต้องการวิเคราะห์ เช่น CPALL, PTT, DELTA"),
    target_price: float = typer.Option(0.0, "--target", "-t", help="ราคาเป้าหมายทำกำไรที่ต้องการ (THB)"),
    timeframe: str = typer.Option("D1", "--tf", help="กรอบเวลาแท่งเทียน: D1, H1, M15"),
):
    """วิเคราะห์หุ้นเจาะลึกแบบ On-Demand (ปัจจัยพื้นฐาน, เทคนิคอล, การคุมความเสี่ยง และบทวิเคราะห์ AI ภาษาไทย)"""
    print_header()
    sym = symbol.strip().upper()

    with console.status(f"[bold yellow]กำลังดึงข้อมูลและประมวลผลโมเดล Quant สำหรับ {sym}..."):
        pipeline = QuantAIPipeline()
        report = pipeline.analyze_symbol(sym, target_price=target_price, timeframe=timeframe)

    # 1. Fundamental Summary Table
    fund_table = Table(title=f"📊 1. ผลการตรวจปัจจัยพื้นฐานเชิงลึก ({sym})", box=box.SIMPLE_HEAVY)
    fund_table.add_column("เกณฑ์การประเมิน", style="bold white")
    fund_table.add_column("ผลลัพธ์เชิงตัวเลข", style="cyan")
    fund_table.add_column("สถานะประเมิน", style="green")
    fund_table.add_column("คำอธิบาย", style="yellow")

    f_score_status = "✅ ผ่านเกณฑ์ (>= 6)" if report.f_score.passed else "⚠️ ไม่ผ่านเกณฑ์ (< 6)"
    fund_table.add_row(
        "Piotroski F-Score (0-9)",
        f"{report.f_score.f_score} / 9",
        f_score_status,
        f"กำไร={report.f_score.positive_roa}, CFO={report.f_score.positive_cfo}, Accrual={report.f_score.accruals_quality}"
    )

    altman_status = f"✅ {report.altman.zone} ZONE" if not report.altman.is_disqualified else "❌ DISTRESS (ตัดสิทธิ์)"
    fund_table.add_row(
        "Altman Z''-Score (Emerging Market)",
        f"{report.altman.z_double_prime:.2f}",
        altman_status,
        f"เกณฑ์ปลอดภัย > 2.60 | เกณฑ์ตัดสิทธิ์ < 1.81 (ความเสี่ยงล้มละลาย)"
    )

    pe_str = f"{report.valuation.pe_ratio:.1f}x" if report.valuation.pe_ratio else "N/A"
    med_str = f"{report.valuation.historical_5yr_pe_median:.1f}x" if report.valuation.historical_5yr_pe_median else "N/A"
    fund_table.add_row(
        "Valuation Percentile (P/E)",
        pe_str,
        f"มัธยฐาน 5 ปี: {med_str}",
        report.valuation.valuation_status_th
    )
    console.print(fund_table)

    # 2. Technical Summary Table
    tech_table = Table(title=f"📈 2. ผลการวิเคราะห์เทคนิคอลเชิงปริมาณ ({sym})", box=box.SIMPLE_HEAVY)
    tech_table.add_column("ระบบวิเคราะห์", style="bold white")
    tech_table.add_column("สัญญาณที่พบ", style="cyan")
    tech_table.add_column("สถานะ", style="green")

    tech_table.add_row(
        "โครงสร้างตลาด Wyckoff",
        f"Trend: {report.wyckoff.trend} | CHoCH: {report.wyckoff.choch_detected} | BOS: {report.wyckoff.bos_detected}",
        report.wyckoff.structure_summary_th,
    )
    tech_table.add_row(
        "Volume Spread Analysis (VSA)",
        f"Stopping Vol: {report.vsa.stopping_volume} | No Supply: {report.vsa.no_supply_bar} | Vol Ratio: {report.vsa.volume_ratio_20sma:.1f}x",
        report.vsa.vsa_summary_th,
    )
    tech_table.add_row(
        "Statistical Confluence",
        f"Triple EMA: {report.confluence.triple_ema_bullish} | RS Line: {report.confluence.relative_strength_bullish} | VCP: {report.confluence.vcp_contraction_detected}",
        report.confluence.confluence_summary_th,
    )
    console.print(tech_table)

    # 3. Risk Management Table
    risk_table = Table(title=f"🛡️ 3. การบริหารความเสี่ยงและขนาดออเดอร์ตามกฎ SET ({sym})", box=box.SIMPLE_HEAVY)
    risk_table.add_column("พารามิเตอร์", style="bold white")
    risk_table.add_column("ค่าที่คำนวณได้", style="cyan")
    risk_table.add_column("กฎเกณฑ์ตลาดหลักทรัพย์แห่งประเทศไทย (SET)", style="magenta")

    risk_table.add_row("ราคาเข้าซื้อ (Entry Price)", f"{report.risk.entry_price:.2f} THB", f"Tick Size: {SETCompliance.get_tick_size(report.risk.entry_price):.2f} THB")
    risk_table.add_row("จุดตัดขาดทุน (Stop Loss ATR-14)", f"{report.risk.stop_loss_price:.2f} THB", f"Dynamic Volatility Stop = Entry - (2.0 * ATR)")
    risk_table.add_row("ราคาเป้าหมาย (Target Price)", f"{report.risk.target_price:.2f} THB", f"Reward-to-Risk: {report.risk.reward_risk_ratio:.2f}:1 ({'ผ่านเกณฑ์ >= 2.0' if report.risk.is_rr_valid else 'ไม่ผ่านเกณฑ์'})")
    risk_table.add_row("ขนาดคำสั่งซื้อ (Shares)", f"{report.risk.shares_allocated:,} หุ้น", f"{report.risk.board_lots:,} Board Lots (ปัดเศษลงตามขั้นต่ำ 100 หุ้น)")
    risk_table.add_row("มูลค่าเงินลงทุน (Trade Value)", f"{report.risk.total_trade_value:,.2f} THB", f"ควบคุมความเสี่ยง {report.risk.risk_percentage:.1f}% ของพอร์ต ({report.risk.risk_amount_thb:,.2f} THB)")
    console.print(risk_table)

    # 4. AI Explainer Panel
    decision_style = "bold green" if report.ai_explainer.decision == MarketDirection.BUY else "bold yellow"
    ai_text = Text()
    ai_text.append(f"\nคำตัดสินของระบบ: {report.ai_explainer.decision.value} (ความเชื่อมั่น {report.ai_explainer.confidence_score:.1f}%)\n", style=decision_style)
    ai_text.append(f"หัวข้อสรุป: {report.ai_explainer.headline_th}\n\n", style="bold white")

    ai_text.append("เหตุผลด้านปัจจัยพื้นฐาน (Fundamental):\n", style="bold cyan")
    for r in report.ai_explainer.fundamental_rationale_th:
        ai_text.append(f"  • {r}\n")

    ai_text.append("\nเหตุผลด้านเทคนิคอลและวอลุ่ม (Technical & VSA):\n", style="bold cyan")
    for r in report.ai_explainer.technical_rationale_th:
        ai_text.append(f"  • {r}\n")

    ai_text.append("\nการบริหารความเสี่ยง (Risk Guard):\n", style="bold cyan")
    for r in report.ai_explainer.risk_rationale_th:
        ai_text.append(f"  • {r}\n")

    ai_text.append(f"\nบทวิเคราะห์สรุป:\n{report.ai_explainer.overall_recommendation_th}\n", style="italic yellow")

    console.print(Panel(ai_text, title="🤖 บทสรุปและคำอธิบายโดย AI Explainer (ภาษาไทย)", box=box.ROUNDED, border_style="bright_green" if report.ai_explainer.decision == MarketDirection.BUY else "yellow"))


@watchlist_app.command("list")
def list_watchlist():
    """แสดงรายชื่อหุ้นทั้งหมดใน Watchlist ที่ผู้ใช้ให้ความสนใจ"""
    print_header()
    pipeline = QuantAIPipeline()
    items = pipeline.watchlist_manager.get_items()

    table = Table(title=f"⭐ รายชื่อหุ้นที่สนใจใน Watchlist ({len(items)} ตัว)", box=box.ROUNDED)
    table.add_column("ลำดับความสำคัญ", style="yellow", justify="center")
    table.add_column("ชื่อหุ้น (Symbol)", style="bold cyan")
    table.add_column("ราคาเป้าหมาย (THB)", style="green", justify="right")
    table.add_column("Tags / หมวดหมู่", style="blue")
    table.add_column("บันทึกย่อของผู้ใช้ (Notes)", style="white")
    table.add_column("การแจ้งเตือน", style="magenta", justify="center")

    for item in items:
        p_stars = "★" * (4 - min(item.priority, 3))
        tp_str = f"{item.target_price:.2f}" if item.target_price else "-"
        tags_str = ", ".join(item.tags) if item.tags else "-"
        alert_str = "🔔 เปิด" if item.alert_on_signal else "🔕 ปิด"
        table.add_row(f"{p_stars} ({item.priority})", item.symbol, tp_str, tags_str, item.notes or "-", alert_str)

    console.print(table)
    console.print("[dim yellow]คำแนะนำ: สามารถเพิ่มหุ้นใหม่ด้วยคำสั่ง 'set-quantai watchlist add <SYMBOL>'[/dim yellow]\n")


@watchlist_app.command("add")
def add_to_watchlist(
    symbol: str = typer.Argument(..., help="ชื่อย่อหุ้นไทยที่ต้องการเพิ่ม เช่น PTT, BDMS, SCB"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="บันทึกย่อส่วนตัวสำหรับหุ้นตัวนี้"),
    target_price: Optional[float] = typer.Option(None, "--target", "-t", help="ราคาเป้าหมายที่สนใจ"),
    priority: int = typer.Option(1, "--priority", "-p", help="ระดับความสำคัญ (1: สูงสุด, 2: กลาง, 3: ต่ำ)"),
    tags: Optional[str] = typer.Option(None, "--tags", help="แท็กคั่นด้วยเครื่องหมายจุลภาค เช่น SET50,DIVIDEND"),
):
    """เพิ่มหุ้นที่สนใจเข้าสู่ระบบ Watchlist เพื่อให้ระบบวิเคราะห์และเฝ้าติดตาม"""
    print_header()
    pipeline = QuantAIPipeline()
    tag_list = [t.strip().upper() for t in tags.split(",")] if tags else []

    item = pipeline.watchlist_manager.add_symbol(
        symbol=symbol,
        notes=notes,
        priority=priority,
        target_price=target_price,
        tags=tag_list,
    )
    console.print(f"[bold green]✅ เพิ่มหุ้น {item.symbol} เข้าสู่ระบบ Watchlist เรียบร้อยแล้ว![/bold green]")
    console.print(f"  • ลำดับความสำคัญ: {item.priority}")
    if item.target_price:
        console.print(f"  • ราคาเป้าหมาย: {item.target_price:.2f} THB")
    if item.notes:
        console.print(f"  • บันทึกย่อ: {item.notes}")
    if item.tags:
        console.print(f"  • หมวดหมู่ Tags: {', '.join(item.tags)}")
    console.print("\n[dim cyan]ทดสอบวิเคราะห์หุ้นตัวนี้ได้ทันทีด้วยคำสั่ง: set-quantai analyze {item.symbol}[/dim cyan]")


@watchlist_app.command("remove")
def remove_from_watchlist(
    symbol: str = typer.Argument(..., help="ชื่อย่อหุ้นไทยที่ต้องการลบออกจาก Watchlist"),
):
    """ลบหุ้นออกจาก Watchlist"""
    print_header()
    pipeline = QuantAIPipeline()
    success = pipeline.watchlist_manager.remove_symbol(symbol)
    if success:
        console.print(f"[bold green]🗑️ ลบหุ้น {symbol.upper()} ออกจาก Watchlist เรียบร้อยแล้ว[/bold green]")
    else:
        console.print(f"[bold red]❌ ไม่พบหุ้น {symbol.upper()} ใน Watchlist[/bold red]")


@app.command("scan")
def scan_all():
    """สแกนและจัดอันดับสัญญาณเทรดสำหรับหุ้นทั้งหมดใน Watchlist"""
    print_header()
    pipeline = QuantAIPipeline()
    symbols = pipeline.watchlist_manager.get_symbols()

    if not symbols:
        console.print("[yellow]⚠️ ยังไม่มีหุ้นใน Watchlist กรุณาเพิ่มหุ้นด้วยคำสั่ง 'set-quantai watchlist add <SYMBOL>' ก่อนครับ[/yellow]")
        return

    console.print(f"[bold cyan]🔍 เริ่มสแกนหุ้นใน Watchlist จำนวน {len(symbols)} ตัว...[/bold cyan]\n")

    table = Table(title="📋 ผลการสแกนสัญญาณเทรดประจำวัน (Watchlist Confluence Ranking)", box=box.ROUNDED)
    table.add_column("หุ้น", style="bold white")
    table.add_column("ราคาล่าสุด", style="cyan", justify="right")
    table.add_column("Piotroski", style="yellow", justify="center")
    table.add_column("Altman Z''", style="magenta", justify="center")
    table.add_column("Wyckoff", style="blue")
    table.add_column("R:R Ratio", style="cyan", justify="right")
    table.add_column("คำตัดสิน AI", style="bold", justify="center")
    table.add_column("ความเชื่อมั่น", style="green", justify="right")

    for sym in symbols:
        report = pipeline.analyze_symbol(sym)
        dec_color = "green" if report.ai_explainer.decision == MarketDirection.BUY else "yellow"
        decision_label = f"[{dec_color}]{report.ai_explainer.decision.value}[/{dec_color}]"

        table.add_row(
            report.symbol,
            f"{report.risk.entry_price:.2f}",
            f"{report.f_score.f_score}/9",
            f"{report.altman.z_double_prime:.2f}",
            report.wyckoff.trend,
            f"{report.risk.reward_risk_ratio:.2f}:1",
            decision_label,
            f"{report.ai_explainer.confidence_score:.1f}%",
        )

    console.print(table)
    console.print("\n[dim green]💡 คุณสามารถดูบทวิเคราะห์ภาษาไทยแบบเต็มของหุ้นแต่ละตัวได้ด้วยคำสั่ง: set-quantai analyze <SYMBOL>[/dim green]\n")


@app.command("rules")
def show_rules():
    """แสดงกฎระเบียบตลาดหลักทรัพย์แห่งประเทศไทย (SET) ที่ระบบนำมาบังคับใช้"""
    print_header()
    table = Table(title="⚖️ กฎเกณฑ์ตลาดหลักทรัพย์แห่งประเทศไทย (SET Compliance)", box=box.ROUNDED)
    table.add_column("ข้อกำหนด", style="bold cyan")
    table.add_column("รายละเอียดและสูตรที่บังคับใช้ในระบบ", style="white")

    table.add_row("1. Board Lot (ขนาดคำสั่งขั้นต่ำ)", "100 หุ้น (ระบบจะทำการปัดเศษลงเสมอ เพื่อป้องกัน Odd Lot)")
    table.add_row("2. Ceiling & Floor Limit", "±30% จากราคาปิดวันก่อนหน้า (คำนวณและปัดตาม Tick Size)")
    table.add_row(
        "3. SET Tick Size Ladder",
        "• ต่ำกว่า 2.00 บาท: 0.01 บาท\n"
        "• 2.00 ถึง < 5.00 บาท: 0.02 บาท\n"
        "• 5.00 ถึง < 10.00 บาท: 0.05 บาท\n"
        "• 10.00 ถึง < 25.00 บาท: 0.10 บาท\n"
        "• 25.00 ถึง < 100.00 บาท: 0.25 บาท\n"
        "• 100.00 ถึง < 200.00 บาท: 0.50 บาท\n"
        "• 200.00 ถึง < 400.00 บาท: 1.00 บาท\n"
        "• 400.00 บาทขึ้นไป: 2.00 บาท"
    )
    table.add_row("4. Portfolio Drawdown Circuit Breaker", "หากพอร์ตขาดทุนในวันเดียวถึง 3.0% ระบบจะตัดการส่งออเดอร์ทันที")
    table.add_row("5. Minimum Reward-to-Risk", "ออเดอร์ต้องมี R:R ไม่ต่ำกว่า 2.0:1 เท่านั้นจึงจะอนุมัติสัญญาณ")
    console.print(table)


@app.command("account")
def show_account():
    """แสดงสถานะบัญชีซื้อขายหลักทรัพย์และเงินทุน (Account & Buying Power)"""
    print_header()
    pipeline = QuantAIPipeline()
    info = pipeline.settrade_client.get_account_info()

    table = Table(title="💼 ข้อมูลบัญชีซื้อขายหลักทรัพย์ (SET Sandbox Trading Account)", box=box.ROUNDED)
    table.add_column("รายการ", style="bold cyan")
    table.add_column("รายละเอียด", style="white")

    table.add_row("เลขที่บัญชีหุ้น (Equity Account)", f"[bold green]{info.get('account_no')}[/bold green]")
    table.add_row("รหัสโบรกเกอร์ (Broker ID)", str(info.get('broker_id')))
    table.add_row("App Code", str(info.get('app_code')))
    table.add_row("รหัส PIN ซื้อขาย", str(info.get('pin')))
    table.add_row("วงเงินซื้อขาย (Credit Limit)", f"{info.get('credit_limit', 0):,.2f} THB")
    table.add_row("เงินสดคงเหลือ (Cash Balance)", f"{info.get('cash_balance', 0):,.2f} THB")
    table.add_row("สถานะระบบ (Status)", f"[bold green]{info.get('status')}[/bold green]")
    table.add_row("โหมดการเชื่อมต่อ (Mode)", f"[yellow]{info.get('mode')}[/yellow]")

    console.print(table)
    console.print("[dim green]✅ บัญชี Kequiv-E พร้อมสำหรับการจำลองและส่งคำสั่งเทรดตามกฎ SET[/dim green]\n")


@app.command("order")
def place_order(
    symbol: str = typer.Argument(..., help="ชื่อย่อหุ้น เช่น PTT, CPALL"),
    side: str = typer.Argument("BUY", help="ฝั่งคำสั่ง: BUY หรือ SELL"),
    shares: int = typer.Argument(100, help="จำนวนหุ้น (ต้องเป็นทวีคูณของ 100 หุ้นตาม Board Lot)"),
    price: float = typer.Argument(..., help="ราคาเสนอซื้อ/ขาย (THB)"),
):
    """ส่งคำสั่งซื้อขายหุ้นเข้าสู่ตลาดจำลอง Sandbox (รองรับกฎ Board Lot & Tick Size)"""
    print_header()
    pipeline = QuantAIPipeline()
    try:
        res = pipeline.settrade_client.place_order(symbol=symbol, side=side, volume=shares, price=price)
        if res.get("status") == "SUCCESS":
            console.print(f"[bold green]🚀 {res.get('message')}[/bold green]")
            console.print(f"  • เลขที่คำสั่ง: {res.get('order_id')}")
            console.print(f"  • มูลค่ารวม: {res.get('trade_value', 0):,.2f} THB")
        else:
            console.print(f"[bold red]❌ เกิดข้อผิดพลาด: {res.get('message')}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]❌ ผิดพลาด: {e}[/bold red]")


@app.command("top5")
def show_top5():
    """แสดง 5 หุ้นแนะนำเด่นประจำวัน พร้อมราคาเข้าซื้อ-เป้าขายทำกำไร และบทวิเคราะห์เจาะลึก"""
    print_header()
    pipeline = QuantAIPipeline()
    with console.status("[bold yellow]กำลังประมวลผลโมเดล Quant คัดกรอง 5 หุ้นแนะนำที่ดีที่สุด..."):
        top5 = TopPicksEngine.get_top5_recommendations(pipeline)

    table = Table(title="🎯 5 หุ้นแนะนำเด่นประจำวัน (Top 5 AI Quant Recommendations)", box=box.ROUNDED)
    table.add_column("อันดับ", style="bold yellow", justify="center")
    table.add_column("หุ้น (Symbol)", style="bold cyan")
    table.add_column("ราคาล่าสุด", style="white", justify="right")
    table.add_column("กรอบเข้าซื้อ (Buy Zone)", style="bold green", justify="center")
    table.add_column("เป้าขาย 1 (Target)", style="bold white", justify="right")
    table.add_column("เป้าขาย 2 (Extended)", style="magenta", justify="right")
    table.add_column("จุดคัท (Cut Loss)", style="bold red", justify="right")
    table.add_column("R:R", style="bold green", justify="center")
    table.add_column("F-Score", style="yellow", justify="center")

    medals = ["🥇 1", "🥈 2", "🥉 3", "⭐ 4", "⭐ 5"]
    for idx, item in enumerate(top5):
        table.add_row(
            medals[idx] if idx < len(medals) else str(item["rank"]),
            item["symbol"],
            f"{item['current_price']:.2f}",
            item["buy_zone"],
            f"{item['target_1']:.2f}",
            f"{item['target_2']:.2f}",
            f"{item['cut_loss']:.2f}",
            f"{item['reward_risk']:.2f}:1",
            f"{item['f_score']}/9",
        )
    console.print(table)

    # Detailed Breakdown for each of the Top 5
    for idx, item in enumerate(top5):
        title_text = f"🔍 อันดับ {item['rank']}: {item['symbol']} ({item['name_th']}) - {item['sector']}"
        detail_text = Text()
        detail_text.append(f"🟢 กรอบราคาเข้าซื้อที่เหมาะสม: {item['buy_zone']} | 🛡️ จุดตัดขาดทุน: {item['cut_loss']:.2f} THB\n", style="bold green")
        detail_text.append(f"🔴 เป้าหมายขายทำกำไร 1: {item['target_1']:.2f} THB (R:R {item['reward_risk']:.2f}:1) | 🚀 เป้าหมาย 2: {item['target_2']:.2f} THB\n", style="bold cyan")
        detail_text.append(f"📦 ขนาดไม้ที่แนะนำ: {item['recommended_shares']:,} หุ้น ({item['recommended_lots']} Lots) มูลค่า {item['trade_value']:,.2f} THB\n\n", style="bold yellow")

        detail_text.append("1. ปัจจัยพื้นฐาน & คุณภาพกำไร:\n", style="bold white")
        detail_text.append(f"   {item['deep_dive']['fundamental_analysis']}\n\n", style="white")

        detail_text.append("2. กราฟเทคนิคอล & พฤติกรรม Smart Money:\n", style="bold white")
        detail_text.append(f"   {item['deep_dive']['technical_analysis']}\n\n", style="white")

        detail_text.append("3. แผนกลยุทธ์ซื้อ-ขาย & การคุมความเสี่ยง:\n", style="bold white")
        detail_text.append(f"   {item['deep_dive']['strategy_and_risk']}\n", style="white")

        console.print(Panel(detail_text, title=title_text, box=box.ROUNDED, border_style="blue"))


@app.command("accuracy")
def check_accuracy(
    execute_buy: bool = typer.Option(False, "--buy", "-b", help="สั่งซื้อ 1,000 หุ้นทั้ง 5 ตัวทันที"),
    simulate_sell: bool = typer.Option(False, "--simulate-sell", "-s", help="จำลองขายตามเป้าหมายเพื่อวัดความแม่นยำ"),
    reset: bool = typer.Option(False, "--reset", "-r", help="รีเซ็ตผลการทดสอบ"),
):
    """ทดสอบความแม่นยำและผลตอบแทนจากการซื้อ 5 หุ้นแนะนำอย่างละ 1,000 หุ้น และขายออกตามเป้าหมายวิเคราะห์"""
    print_header()
    pipeline = QuantAIPipeline()

    if reset:
        res = AutoTraderEngine.reset_data()
        console.print(f"[bold yellow]🔄 {res['message']}[/bold yellow]")
        return

    if execute_buy:
        with console.status("[bold green]กำลังส่งคำสั่งซื้อ 1,000 หุ้น สำหรับ Top 5..."):
            res = AutoTraderEngine.execute_top5_purchases(pipeline, shares_per_stock=1000)
        console.print(f"[bold green]✅ {res['message']}[/bold green]\n")

    if simulate_sell:
        with console.status("[bold blue]กำลังประมวลผลจำลองการขายออกตามเป้าหมายวิเคราะห์ (Target 1)..."):
            AutoTraderEngine.simulate_target_exits(pipeline)
        console.print("[bold blue]🎯 คำนวณและปิดคำสั่งขายตามเป้าหมายเรียบร้อยแล้ว[/bold blue]\n")

    # Fetch and display performance summary
    summary = AutoTraderEngine.get_performance_summary(pipeline)

    # 1. KPI Panel
    kpi_text = Text()
    kpi_text.append("🎯 ความแม่นยำของการวิเคราะห์ (Accuracy / Win Rate): ", style="bold white")
    kpi_text.append(f"{summary['accuracy_percent']}%\n", style="bold green" if summary['accuracy_percent'] >= 70 else "bold yellow")
    kpi_text.append(f"   (ชนะ {summary['winning_trades']} / แพ้ {summary['losing_trades']} จากการเทรดปิดสถานะ {summary['closed_trades_count']} ไม้)\n\n", style="cyan")

    sign = "+" if summary['total_realized_profit'] > 0 else ""
    kpi_text.append("💰 กำไรสุทธิรวม (Total Realized Profit): ", style="bold white")
    kpi_text.append(f"{sign}{summary['total_realized_profit']:,.2f} THB ", style="bold green" if summary['total_realized_profit'] >= 0 else "bold red")
    kpi_text.append(f"({sign}{summary['return_percent']}% จากเงินลงทุน {summary['total_invested']:,.2f} THB)\n", style="green")

    console.print(Panel(kpi_text, title="🏆 สรุปผลการทดสอบความแม่นยำ & ประสิทธิภาพ AI", box=box.ROUNDED, border_style="green"))

    # 2. Detailed Trades Table
    table = Table(title="📊 รายละเอียดการซื้อ-ขายหุ้น Top 5 (ตัวละ 1,000 หุ้น)", box=box.SIMPLE_HEAVY)
    table.add_column("หุ้น", style="bold white")
    table.add_column("จำนวน", style="cyan", justify="right")
    table.add_column("ราคาซื้อ", style="white", justify="right")
    table.add_column("เป้าขาย 1", style="bold green", justify="right")
    table.add_column("จุดคัท", style="red", justify="right")
    table.add_column("ราคาขาย", style="bold white", justify="right")
    table.add_column("กำไร (THB)", style="bold green", justify="right")
    table.add_column("ผลตอบแทน (%)", style="bold green", justify="right")
    table.add_column("สถานะ", style="bold yellow", justify="center")

    all_trades = (summary.get("closed_trades", []) or []) + (summary.get("positions", []) or [])
    for t in all_trades:
        is_open = t.get("status") == "OPEN"
        exit_p = (t.get("current_price") or t["buy_price"]) if is_open else t["exit_price"]
        pl = t.get("unrealized_pl", 0) if is_open else t.get("realized_pl", 0)
        pl_pct = t.get("unrealized_pct", 0) if is_open else t.get("realized_pct", 0)
        status_label = "⏳ ถือรอเป้าหมาย" if is_open else "🎯 บรรลุเป้าหมาย 1"

        table.add_row(
            t["symbol"],
            f"{t['shares']:,}",
            f"{t['buy_price']:.2f}",
            f"{t['target_1']:.2f}",
            f"{t['cut_loss']:.2f}",
            f"{exit_p:.2f}",
            f"{pl:+,.2f}",
            f"{pl_pct:+.2f}%",
            status_label,
        )
    console.print(table)


@app.command("dashboard")
def start_dashboard(
    port: int = typer.Option(8555, "--port", "-p", help="พอร์ตสำหรับเปิดหน้าเว็บ Dashboard"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host IP"),
):
    """เปิดหน้าเว็บ Dashboard ภาษาไทยแบบ Interactive บน Web Browser"""
    print_header()
    import uvicorn
    console.print(f"[bold green]🚀 กำลังเปิดหน้าเว็บ Web Dashboard ที่ http://localhost:{port}[/bold green]")
    console.print(f"[dim yellow]คุณสามารถเปิดเบราว์เซอร์ไปที่ http://localhost:{port} เพื่อใช้งานระบบแบบกราฟิกได้ทันที![/dim yellow]\n")
    uvicorn.run("set_quantai.web_app:web_app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()
