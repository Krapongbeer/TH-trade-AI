# 📈 SET-QuantAI: ระบบวิเคราะห์เชิงปริมาณและสัญญาณเทรดหุ้นไทยอัตโนมัติ

ระบบวิเคราะห์หุ้นไทยเชิงปริมาณ (Quantitative Analysis) และระบบตัดสินใจส่งคำสั่งซื้อขายอัตโนมัติ (Automated Trading System) สำหรับตลาดหลักทรัพย์แห่งประเทศไทย (SET) ที่ออกแบบตามมาตรฐานสถาบันการเงิน โดยแยกส่วนคำนวณทางคณิตศาสตร์ที่เคร่งครัด (**Deterministic Rule Engine**) ออกจากส่วนสร้างบทวิเคราะห์อธิบายผลลัพธ์ (**AI Explainer**) อย่างเด็ดขาด พร้อมรองรับการกำหนดและบริหารรายการหุ้นที่สนใจ (**Watchlist & Custom Focus List**)

---

## 🌟 จุดเด่นและมาตรฐานของระบบ

1. **สอดคล้องกับกฎเกณฑ์ตลาดหลักทรัพย์แห่งประเทศไทย (SET Compliance)**:
   - **Board Lot 100 หุ้น**: คำนวณขนาดไม้ (Position Sizing) แล้วปัดเศษลงเป็นทวีคูณของ 100 หุ้นเสมอ ป้องกันการเกิดเศษหุ้น (Odd Lot)
   - **SET Tick Size Ladder**: ปรับราคาเข้าซื้อ จุดตัดขาดทุน และเป้าหมายตามช่วงขั้นราคาจริงของ SET (ตั้งแต่ 0.01 ถึง 2.00 บาท)
   - **Ceiling / Floor Limit**: ตรวจสอบกรอบราคาสูงสุด-ต่ำสุดประจำวัน ($\pm$30%)
2. **โมเดลการเงินเชิงปริมาณที่ผ่านการพิสูจน์ (Audited Quant Models)**:
   - **Piotroski F-Score (0-9)**: วัดความแข็งแกร่ง 3 มิติ (ความสามารถทำกำไร, สภาพคล่อง/หนี้สิน, ประสิทธิภาพดำเนินงาน) ผ่านเกณฑ์เมื่อได้คะแนน $\ge 6$
   - **Altman Z''-Score (Emerging Market Model)**: คัดกรองความเสี่ยงล้มละลาย ตัดสิทธิ์หุ้นที่ได้ $Z'' < 1.81$ (Distress Zone) ทันที
   - **Valuation Percentile**: เปรียบเทียบ P/E, P/BV กับค่ามัธยฐานย้อนหลัง 5 ปี และ Percentile ของกลุ่มอุตสาหกรรม
3. **การวิเคราะห์เทคนิคอลเชิงสถิติ (Quantitative Technical Engine)**:
   - **Wyckoff Market Structure**: ตรวจหา Fractal Pivots (Higher-High/Higher-Low) และสัญญาณ CHoCH / BOS
   - **Volume Spread Analysis (VSA)**: ตรวจจับ Stopping Volume (Smart Money ดูดซับแรงขาย) และ No Supply Bar (ย่อตัววอลุ่มแห้ง)
   - **Triple EMA & RS Line**: ตรวจสอบการเรียงตัวของแนวโน้ม (EMA 20 > 50 > 200) และ Relative Strength เทียบดัชนี SET
4. **การบริหารความเสี่ยงขั้นสูง (Risk Guard)**:
   - Dynamic Volatility Stop Loss อิง ATR-14: $\text{Entry} - (2.0 \times \text{ATR}_{14})$
   - Reward-to-Risk (R:R) Execution Gate: ต้องมี R:R ไม่ต่ำกว่า **2.0:1** เท่านั้น
   - Daily Drawdown Circuit Breaker: ระงับการส่งคำสั่งทันทีหากพอร์ตขาดทุนสะสมในวันเดียวแตะ 3.0%
5. **ระบบหุ้นที่สนใจ (Watchlist & Custom Focus List)**:
   - ให้ผู้ใช้สามารถเพิ่ม/ลบ/จัดกลุ่มหุ้นที่สนใจ พร้อมบันทึกย่อ (Notes), ราคาเป้าหมาย (Target Price), ระดับความสำคัญ และหมวดหมู่ Tags
   - สั่งสแกนหุ้นใน Watchlist พร้อมกัน หรือวิเคราะห์เจาะลึกแบบ On-Demand ได้ทันที

---

## 📂 โครงสร้างไดเรกทอรีของโปรเจกต์

```text
TH-trade-AI/
├── config/
│   ├── settings.yaml                  # การตั้งค่าระบบ (ฐานข้อมูล, Redis, Settrade, พารามิเตอร์ความเสี่ยง)
│   └── watchlist.yaml                 # ข้อมูลหุ้นที่สนใจ (Watchlist, Notes, Priority, Target)
├── docker-compose.yml                 # TimescaleDB (PostgreSQL 16) + Redis 7
├── file.md                            # ข้อกำหนดสถาปัตยกรรมระบบ (Architecture Specification)
├── pyproject.toml                     # Poetry Project Specification
├── run.sh                             # สคริปต์เรียกใช้งาน CLI สะดวกสบาย
├── tests/
│   └── test_quantai.py                # ชุดทดสอบ Unit & Integration Tests
└── set_quantai/
    ├── cli.py                         # ระบบโต้ตอบภาษาไทยผ่าน Terminal (Rich & Typer)
    ├── config.py                      # ตัวโหลด Settings ผ่าน Pydantic v2
    ├── core/
    │   ├── compliance.py              # กฎเกณฑ์ SET: Board Lot, Tick Ladder, Ceiling/Floor
    │   ├── models.py                  # Pydantic Data Models ทั้งหมดของระบบ
    │   └── pipeline.py                # Pipeline ศูนย์กลางที่เชื่อมต่อทั้ง 5 โมดูล
    ├── data_engine/
    │   ├── settrade_client.py         # Settrade Open API (Real-time, Level-2 Depth, OHLCV)
    │   ├── sec_client.py              # SEC Open API (แบบ 59-2, 246-2, Cash Balance)
    │   ├── financial_statements.py    # จัดการงบการเงินย้อนหลัง 5 ปีระดับไตรมาส
    │   └── normalizer.py              # ปรับราคา Corporate Actions และ Resampling
    ├── fundamental_screener/
    │   ├── piotroski.py               # Piotroski F-Score (เกณฑ์ 0-9)
    │   ├── altman_z.py                # Altman Z''-Score (Emerging Market)
    │   └── valuation.py               # P/E, P/BV vs 5-Yr Median & Sector Bands
    ├── technical_analyser/
    │   ├── wyckoff_structure.py       # Fractal Pivots, CHoCH, BOS
    │   ├── vsa.py                     # Stopping Volume & No Supply Bar
    │   └── confluence.py              # Triple EMA (20>50>200), RS Line, VCP
    ├── risk_guard/
    │   └── risk_manager.py            # Position Sizing, ATR Stop, Circuit Breaker
    ├── watchlist_manager/
    │   └── manager.py                 # จัดการหุ้นที่สนใจ (CRUD, YAML Sync, Filters)
    ├── ai_explainer/
    │   └── explainer.py               # สร้างบทวิเคราะห์และคำอธิบายภาษาไทย (Pydantic Validated)
    └── database/
        └── schema.sql                 # TimescaleDB Hypertables & Schemas
```

---

## 🚀 วิธีการติดตั้งและการใช้งาน

### 1. การติดตั้งและการเตรียมสภาพแวดล้อม
โปรเจกต์นี้ใช้ Python 3.11+ พร้อม Virtual Environment ในโฟลเดอร์ `.venv`

```bash
# ตรวจสอบสถานะการทำงานของ CLI
./run.sh --help
```

---

### 2. การจัดการ "หุ้นที่สนใจ" (Watchlist Management)

#### ดูรายชื่อหุ้นที่สนใจใน Watchlist:
```bash
./run.sh watchlist list
```

#### เพิ่มหุ้นที่สนใจเข้าสู่ระบบ:
```bash
./run.sh watchlist add PTT --notes "หุ้นพลังงานขนาดใหญ่ ปันผลสูง" --target 42.0 --priority 1 --tags "ENERGY,SET50"
./run.sh watchlist add GULF --notes "จับตาเบรกเอาต์" --target 52.0 --priority 1 --tags "POWER,GROWTH"
```

#### ลบหุ้นออกจาก Watchlist:
```bash
./run.sh watchlist remove GULF
```

---

### 3. การวิเคราะห์หุ้นเจาะลึกแบบ On-Demand (`analyze`)

สั่งให้ระบบวิเคราะห์หุ้นตัวที่สนใจทันที โดยระบบจะดึงงบการเงินย้อนหลัง คำนวณ F-Score, Altman Z'', โครงสร้างกราฟ Wyckoff, VSA, Triple EMA, ประเมิน R:R และคำนวณจำนวนหุ้นตาม Board Lot พร้อมสรุปคำอธิบายภาษาไทย:

```bash
./run.sh analyze PTT
./run.sh analyze CPALL
./run.sh analyze DELTA --target 175.0
```

---

### 4. การสแกนสัญญาณเทรดสำหรับหุ้นใน Watchlist พร้อมกัน (`scan`)

สแกนหุ้นทุกตัวใน Watchlist เพื่อจัดอันดับความน่าสนใจและตรวจหาสัญญาณคอนเฟิร์ม (Confluence Confirmation):

```bash
./run.sh scan
```

---

### 5. การดูกฎเกณฑ์ตลาดหลักทรัพย์แห่งประเทศไทย (`rules`)

```bash
./run.sh rules
```

---

### 6. การรันชุดทดสอบ (Automated Unit Tests)

```bash
.venv/bin/python tests/test_quantai.py
```
*ชุดทดสอบครอบคลุม: SET Tick sizes, Board Lot 100 หุ้น, Ceiling/Floor, Piotroski 9-criteria, Altman Z'', Risk Sizing และ Watchlist CRUD*

---

### 7. การเปิดใช้งาน Database (TimescaleDB & Redis) ผ่าน Docker

```bash
docker compose up -d
```
ระบบจะสร้าง Container สำหรับ TimescaleDB (PostgreSQL 16) และ Redis 7 พร้อมติดตั้ง Schema ให้อัตโนมัติ
