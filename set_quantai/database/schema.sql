-- SET-QuantAI Database Schema for TimescaleDB / PostgreSQL

CREATE TABLE IF NOT EXISTS instruments (
    symbol VARCHAR(10) PRIMARY KEY,
    name_th VARCHAR(100),
    sector VARCHAR(50),
    market VARCHAR(10),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_data_daily (
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

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('market_data_daily', 'time', if_not_exists => TRUE);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS fundamental_metrics (
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

CREATE TABLE IF NOT EXISTS trade_signals (
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

CREATE TABLE IF NOT EXISTS user_watchlists (
    watchlist_id UUID PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    watchlist_id UUID REFERENCES user_watchlists(watchlist_id) ON DELETE CASCADE,
    symbol VARCHAR(10) REFERENCES instruments(symbol) ON DELETE CASCADE,
    notes TEXT,
    priority INT DEFAULT 1,
    target_price NUMERIC(10, 2),
    alert_on_signal BOOLEAN DEFAULT TRUE,
    added_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (watchlist_id, symbol)
);
