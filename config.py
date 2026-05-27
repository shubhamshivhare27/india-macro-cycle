# ============================================================
#  INDIA MACRO CYCLE SYSTEM — CONFIG
#  Edit this file before first run
# ============================================================

from pathlib import Path

# ── Folder & Excel paths ──────────────────────────────────────
BASE_DIR        = Path(r"C:\Users\shubh\Documents\Personal\MBAEx\All Terms\Term-6\AVI 2")
EXCEL_PATH      = BASE_DIR / "Sector_Rotation_New Feb 24.xlsx"
EXCEL_SHEET     = "🌀 Business Cycle Analysis"

DATA_DIR        = BASE_DIR / "macro-cycle-system" / "data"
LOGS_DIR        = BASE_DIR / "macro-cycle-system" / "logs"
DASHBOARD_DIR   = BASE_DIR / "macro-cycle-system" / "dashboard"

SNAPSHOT_FILE   = DATA_DIR / "macro_snapshot.json"
HISTORY_FILE    = DATA_DIR / "macro_history.csv"
OVERRIDES_FILE  = DATA_DIR / "manual_overrides.json"
LOG_FILE        = LOGS_DIR / "macro_run.log"

# ── Email settings ────────────────────────────────────────────
GMAIL_USER      = "your@gmail.com"          # ← edit
GMAIL_PASS      = "your-app-password"       # ← edit (Gmail App Password)
RECIPIENT_EMAIL = "recipient@gmail.com"     # ← edit

# ── Google Sheet for manual / paywalled values ────────────────
# Share the sheet publicly (viewer) and paste the CSV export URL here
# File → Share → Anyone with link (Viewer) → Copy link
# Then change /edit to /export?format=csv
GSHEET_CSV_URL  = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv"
# ← Set to "" to disable Google Sheet; values will be prompted in terminal instead

# ── EXACT CELL MAP (confirmed from Excel audit) ──────────────
#    These are the INPUT cells in column B that Python writes to.
#    All other cells (F, G, H, I, E39, F49, H49) are formula-driven — NEVER touched.
CELL_MAP = {
    "nifty_6m_change":        "B8",   # Leading  | Nifty 50 6M Price Change (%)
    "pmi_manufacturing":      "B9",   # Leading  | PMI Manufacturing (Current)
    "repo_rate_trend":        "B10",  # Leading  | RBI Repo Rate Trend (3M Change bps)
    "credit_growth":          "B11",  # Leading  | Credit Growth YoY %
    "housing_starts":         "B12",  # Leading  | Housing Starts / New Launches
    "gdp_growth":             "B16",  # Coincident | GDP Growth QoQ Annualized (%)
    "iip_growth":             "B17",  # Coincident | IIP Industrial Production YoY %
    "earnings_growth":        "B18",  # Coincident | Corporate Earnings Growth (Nifty)
    "auto_sales":             "B19",  # Coincident | Auto Sales YoY %
    "gst_collections":        "B20",  # Coincident | GST Collection YoY %
    "cpi_inflation":          "B24",  # Lagging  | CPI Inflation (%)
    "unemployment_rate":      "B25",  # Lagging  | Unemployment Rate (%)
    "bank_npa_ratio":         "B26",  # Lagging  | Bank NPA Ratio (%)
    "current_account_deficit":"B27",  # Lagging  | Current Account Deficit (% GDP)
    "wpi_inflation":          "B28",  # Lagging  | WPI Inflation (%)
}

# ── OUTPUT cells (read-only, formula-driven) ─────────────────
OUTPUT_CELLS = {
    "composite_score": "E39",  # Main composite score  (0.000 → 1.000)
    "score_check":     "F49",  # Duplicate score display
    "phase_label":     "H49",  # e.g. "🟢 STRONG RECOVERY — Max Cyclical Exposure"
}

# ── Data-fetch status: AUTO vs MANUAL/PAYWALL ─────────────────
# AUTO   = fetched from free official sources
# GSHEET = you enter in Google Sheet; Python reads it
# MANUAL = prompted in terminal if GSHEET_CSV_URL not set
FETCH_MODE = {
    "nifty_6m_change":        "AUTO",    # yfinance ^NSEI
    "pmi_manufacturing":      "GSHEET",  # S&P Global — PAYWALL
    "repo_rate_trend":        "AUTO",    # RBI website
    "credit_growth":          "AUTO",    # RBI DBIE
    "housing_starts":         "GSHEET",  # No official real-time API
    "gdp_growth":             "AUTO",    # MOSPI data.gov.in
    "iip_growth":             "AUTO",    # MOSPI data.gov.in
    "earnings_growth":        "GSHEET",  # NSE/Bloomberg — no free API
    "auto_sales":             "AUTO",    # SIAM (scraped)
    "gst_collections":        "AUTO",    # Finance Ministry (scraped)
    "cpi_inflation":          "AUTO",    # MOSPI data.gov.in
    "unemployment_rate":      "GSHEET",  # CMIE — PAYWALL
    "bank_npa_ratio":         "AUTO",    # RBI FSR report
    "current_account_deficit":"AUTO",    # RBI / MOSPI
    "wpi_inflation":          "AUTO",    # DPIIT data.gov.in
}

# ── Indicator display metadata ────────────────────────────────
INDICATOR_META = {
    "nifty_6m_change":        {"label": "Nifty 50 6M Price Change",    "unit": "%",       "group": "Leading",    "invert": False},
    "pmi_manufacturing":      {"label": "PMI Manufacturing",           "unit": "index",   "group": "Leading",    "invert": False},
    "repo_rate_trend":        {"label": "RBI Repo Rate Trend (3M)",    "unit": "bps",     "group": "Leading",    "invert": False},
    "credit_growth":          {"label": "Credit Growth YoY",           "unit": "%",       "group": "Leading",    "invert": False},
    "housing_starts":         {"label": "Housing Starts / New Launches","unit":"text",    "group": "Leading",    "invert": False},
    "gdp_growth":             {"label": "GDP Growth QoQ Annualised",   "unit": "%",       "group": "Coincident", "invert": False},
    "iip_growth":             {"label": "IIP Industrial Production",   "unit": "% YoY",  "group": "Coincident", "invert": False},
    "earnings_growth":        {"label": "Corporate Earnings Growth",   "unit": "%",       "group": "Coincident", "invert": False},
    "auto_sales":             {"label": "Auto Sales YoY",              "unit": "%",       "group": "Coincident", "invert": False},
    "gst_collections":        {"label": "GST Collections YoY",        "unit": "%",       "group": "Coincident", "invert": False},
    "cpi_inflation":          {"label": "CPI Inflation",               "unit": "%",       "group": "Lagging",    "invert": True},
    "unemployment_rate":      {"label": "Unemployment Rate",           "unit": "%",       "group": "Lagging",    "invert": True},
    "bank_npa_ratio":         {"label": "Bank NPA Ratio",              "unit": "%",       "group": "Lagging",    "invert": True},
    "current_account_deficit":{"label": "Current Account Deficit",    "unit": "% GDP",   "group": "Lagging",    "invert": True},
    "wpi_inflation":          {"label": "WPI Inflation",               "unit": "%",       "group": "Lagging",    "invert": True},
}

# ── Cycle phase → sector strategy map (4 phases — Merrill Lynch India Model, May 2026) ───
# Phase 1: STRONG RECOVERY   (score 0.80–1.00) = Early Expansion, GDP rebounds
# Phase 2: MID EXPANSION     (score 0.60–0.80) = Mid Cycle, strong GDP + credit
# Phase 3: LATE CYCLE        (score 0.40–0.60) = Peak, GDP plateaus, inflation high
# Phase 4: CONTRACTION       (score 0.20–0.40) = Slowdown, GDP <5%, rate cuts begin
# Below 0.20: also CONTRACTION (deep contraction)
SECTOR_STRATEGY = {
    "STRONG RECOVERY": {
        "score_range": (0.80, 1.00),
        "overweight":    ["Nifty Bank / Financials", "Nifty Realty", "Nifty Auto", "Nifty Infra"],
        "neutral":       ["Nifty IT", "Nifty Healthcare"],
        "underweight":   ["Nifty Energy", "Nifty Metal", "Nifty FMCG", "Nifty Pharma"],
        "action":        "Credit cycle turns up. Overweight Financials, Real Estate, Consumer Discretionary, Industrials. Capex plans announced.",
        "etfs":          {"BANKBEES.NS":"OW","PSUBNKBEES.NS":"OW","INFRABEES.NS":"OW","AUTOBEES.NS":"OW",
                          "ITBEES.NS":"N","PHARMABEES.NS":"UW","FMCGBEES.NS":"UW",
                          "METALBEES.NS":"UW","ENERGYBEES.NS":"UW"},
    },
    "MID EXPANSION": {
        "score_range": (0.60, 0.80),
        "overweight":    ["Nifty IT", "Nifty Metal", "Nifty Energy", "Nifty Infra"],
        "neutral":       ["Nifty Bank / Financials", "Nifty Auto"],
        "underweight":   ["Nifty Pharma", "Nifty FMCG", "Nifty Healthcare"],
        "action":        "Strong earnings growth. IT + Materials/Metals + Energy + Capex industrials. Commodity cycle up. Global IT demand rises.",
        "etfs":          {"ITBEES.NS":"OW","METALBEES.NS":"OW","ENERGYBEES.NS":"OW","INFRABEES.NS":"OW",
                          "BANKBEES.NS":"N","AUTOBEES.NS":"N",
                          "PHARMABEES.NS":"UW","FMCGBEES.NS":"UW"},
    },
    "LATE CYCLE": {
        "score_range": (0.40, 0.60),
        "overweight":    ["Nifty Energy", "Nifty Metal", "Nifty Healthcare", "Nifty FMCG"],
        "neutral":       ["Nifty IT", "Nifty Infra"],
        "underweight":   ["Nifty Bank / Financials", "Nifty Realty", "Nifty Auto"],
        "action":        "Inflation hedge. Defensive rotation. Rate sensitivity hits banks/realty. Energy and materials at commodity peak.",
        "etfs":          {"ENERGYBEES.NS":"OW","METALBEES.NS":"OW","PHARMABEES.NS":"OW","FMCGBEES.NS":"OW",
                          "ITBEES.NS":"N","INFRABEES.NS":"N",
                          "BANKBEES.NS":"UW","AUTOBEES.NS":"UW","PSUBNKBEES.NS":"UW"},
    },
    "CONTRACTION": {
        "score_range": (0.00, 0.40),
        "overweight":    ["Nifty FMCG", "Nifty Healthcare", "Nifty Pharma", "Nifty IT"],
        "neutral":       ["Nifty Energy"],
        "underweight":   ["Nifty Bank / Financials", "Nifty Realty", "Nifty Metal", "Nifty Auto", "Nifty Infra"],
        "action":        "Earnings visibility, inelastic demand, safe-haven, dividend yield. Avoid all cyclicals.",
        "etfs":          {"FMCGBEES.NS":"OW","PHARMABEES.NS":"OW","ITBEES.NS":"OW",
                          "ENERGYBEES.NS":"N",
                          "BANKBEES.NS":"UW","METALBEES.NS":"UW","AUTOBEES.NS":"UW",
                          "INFRABEES.NS":"UW","PSUBNKBEES.NS":"UW"},
    },
}

# ── Scheduling ────────────────────────────────────────────────
SCHEDULE_DAY    = "monday"   # Run every Monday
SCHEDULE_TIME   = "08:00"    # 8:00 AM
