# Role & Instruction for Antigravity
Role: Lead Quantitative Financial Software Architect & Full-Stack Python Engineer.
Task: Build a complete, production-ready Thai Equity Quantitative Analysis & Automated Trading System (SET-QuantAI) based on the comprehensive specification below.

System Constraints & Standards:
1. Core Stack: Python 3.11+, Poetry, TimescaleDB (PostgreSQL), Redis (Pub/Sub & Caching).
2. Theoretical Rigor: Strictly use audited quantitative models (Piotroski F-Score, Altman Z''-Score, Extended DuPont, Wyckoff Market Structure, VSA, ATR Position Sizing). No random or speculative LLM outputs.
3. Market Compliance: Implement Stock Exchange of Thailand (SET) rules: 100-share Board Lots, SET Tick Size ladder (0.01 to 2.00 THB), and Ceiling/Floor limits (±30%).
4. Architecture: Decouple Quantitative Logic (Deterministic Rule Engine) from the AI Explainer (LLM Reasoner with Pydantic JSON validation).

---

# Architecture & Technical Specification: Thai Equity Quantitative System (SET-QuantAI)

## 1. System Modules Specification

### Module 1: Data Ingestion & Storage (`data_engine`)
- **Data Providers**:
  - `Settrade Open API`: Real-time quote, Level-2 Market Depth, Tick data, Historical EOD/Intraday OHLCV.
  - `SEC Open API`: Corporate disclosures (Form 246-2, Form 59-2), Cash Balance & Trading Alert lists.
  - `Financial Statements Engine`: 5-year quarterly Balance Sheets, Income Statements, and Cash Flow Statements.
- **Normalization Rules**:
  - Auto-adjust historical price series for Corporate Actions (XD, XR, XW, Splits).
  - Multi-timeframe resampling: `M15`, `H1`, `H4`, `D1`, `W1`.
  - Persist normalized data into TimescaleDB hypertables.

### Module 2: Deep Fundamental Engine (`fundamental_screener`)
1. **Piotroski F-Score (0 to 9)**:
   - Profitability: ROA > 0, CFO > 0, ΔROA > 0, Accruals (CFO > Net Income).
   - Leverage/Liquidity: ΔLong-term Debt ≤ 0, ΔCurrent Ratio > 0, Dilution check (no share issuance).
   - Operating Efficiency: ΔGross Margin > 0, ΔAsset Turnover > 0.
   - Threshold: Pass if F-Score ≥ 6.
2. **Altman Z-Score (Emerging Market Model - Z'')**:
   - Formula: Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
     (X1 = Working Capital/Total Assets, X2 = Retained Earnings/Total Assets, X3 = EBIT/Total Assets, X4 = Book Value Equity/Total Liabilities)
   - Filter Rule: Disqualify any stock with Z'' < 1.81.
3. **Valuation Metrics**: Compare P/E, P/BV, EV/EBITDA against 5-Year Historical Medians and Sector-relative Percentile Bands.

### Module 3: Quantitative Technical Engine (`technical_analyser`)
1. **Market Structure (Wyckoff & Trend)**:
   - Detect High-High/High-Low (Uptrend) vs Low-High/Low-Low via Fractal Pivot algorithms.
   - Identify Change of Character (CHoCH) and Break of Structure (BOS).
2. **Volume Spread Analysis (VSA)**:
   - Stopping Volume: Tight spread / long lower shadow with ultra-high volume.
   - No Supply Bar: Low-volume pullback below 20-day Volume SMA.
3. **Indicators & Statistical Confluence**:
   - Triple EMA Alignment: EMA 20 > EMA 50 > EMA 200.
   - Relative Strength Line: RS = Close(Stock) / Close(SET Index) trending upward.
   - Volatility Contraction Pattern (VCP): Standard deviation and ATR contraction before breakout.

### Module 4: Risk Management & Position Sizing (`risk_guard`)
1. **Position Sizing Formula**:
   $$\text{Position Size (Shares)} = \frac{\text{Account Capital} \times \text{Risk Percentage}}{\text{Entry Price} - \text{Stop Loss Price}}$$
   - Max Risk per Trade: 1.0% to 1.5% of total portfolio equity.
   - Shares must be rounded down to multiples of 100 (Board Lot).
2. **Dynamic Volatility Stop Loss**:
   $$\text{Initial Stop} = \text{Entry} - (2.0 \times \text{ATR}_{14})$$
3. **Execution Gate**: Minimum Reward-to-Risk (R:R) ratio must be ≥ 2.0:1.
4. **Circuit Breakers**: Daily portfolio drawdown threshold at 3.0%. If breached, halt order generation immediately.

### Module 5: Watchlist & Custom Universe Management (`watchlist_manager`)
1. **Custom Watchlist Configuration**:
   - Allow users to add, update, and categorize custom focus stocks (Tags, Priority, Target Price, Custom Notes).
   - Ingestion methods: CLI command (e.g., `set-quantai watchlist add PTT CPALL`), REST API / Web UI, and config files (`config/watchlist.yaml`).
2. **Analysis Execution Modes**:
   - **On-Demand Deep-Dive**: Trigger on-demand full quantitative analysis for any single symbol or watchlist group (Fundamental scores, Wyckoff structure, VSA, Valuation percentile, and AI explanation report in Thai).
   - **Priority Monitoring & Alerting**: Continuously scan watchlist symbols on intraday timeframes (`M15`, `H1`) and trigger instant alerts when entry criteria, VSA Stopping Volume, or Breakout conditions are met.

---

## 2. Database Schema (TimescaleDB / PostgreSQL)

```sql
CREATE TABLE instruments (
    symbol VARCHAR(10) PRIMARY KEY,
    name_th VARCHAR(100),
    sector VARCHAR(50),
    market VARCHAR(10),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE market_data_daily (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) REFERENCES instruments(symbol),
    open NUMERIC(10, 2) NOT NULL,
    high NUMERIC(10, 2) NOT NULL,
    low NUMERIC(10, 2) NOT NULL,
    close NUMERIC(10, 2) NOT NULL,
    volume BIGINT NOT NULL,
    value NUMERIC(15, 2) NOT NULL,
    adjusted_close NUMERIC(10, 2) NOT NULL
);
SELECT create_hypertable('market_data_daily', 'time', if_not_exists => TRUE);

CREATE TABLE fundamental_metrics (
    period_date DATE NOT NULL,
    symbol VARCHAR(10) REFERENCES instruments(symbol),
    piotroski_score INT CHECK (piotroski_score BETWEEN 0 AND 9),
    altman_z_score NUMERIC(6, 3),
    pe_ratio NUMERIC(8, 2),
    pbv_ratio NUMERIC(8, 2),
    roe NUMERIC(6, 2),
    cfo_to_net_income NUMERIC(6, 2),
    PRIMARY KEY (period_date, symbol)
);

CREATE TABLE trade_signals (
    signal_id UUID PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) REFERENCES instruments(symbol),
    direction VARCHAR(4) CHECK (direction IN ('BUY', 'SELL')),
    strategy_name VARCHAR(50),
    entry_price NUMERIC(10, 2) NOT NULL,
    stop_loss NUMERIC(10, 2) NOT NULL,
    target_1 NUMERIC(10, 2) NOT NULL,
    allocated_shares INT NOT NULL,
    risk_reward_ratio NUMERIC(4, 2) NOT NULL,
    rationale JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING'
);

CREATE TABLE user_watchlists (
    watchlist_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE watchlist_items (
    watchlist_id UUID REFERENCES user_watchlists(watchlist_id) ON DELETE CASCADE,
    symbol VARCHAR(10) REFERENCES instruments(symbol) ON DELETE CASCADE,
    notes TEXT,
    priority INT DEFAULT 1,
    target_price NUMERIC(10, 2),
    alert_on_signal BOOLEAN DEFAULT TRUE,
    added_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (watchlist_id, symbol)
);
```
