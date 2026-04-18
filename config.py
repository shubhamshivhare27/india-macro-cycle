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

# ── Cycle phase → sector strategy map (from PPT + Excel) ─────
SECTOR_STRATEGY = {
    "STRONG RECOVERY": {
        "score_range": (0.80, 1.00),
        "overweight":    ["Nifty Realty", "Nifty Metal", "Nifty PSU Bank", "Nifty Bank", "Nifty Auto"],
        "neutral":       ["Nifty IT", "Nifty Infra", "Nifty Energy"],
        "underweight":   ["Nifty FMCG", "Nifty Pharma", "Nifty Healthcare"],
        "action":        "Maximum equity; overweight beaten-down cyclicals. Start watching for cycle-peak reversal.",
        "etfs":          {"BANKBEES.NS":"OW","PSUBNKBEES.NS":"OW","SETFNIF50.NS":"OW",
                          "ITBEES.NS":"N","PHARMABEES.NS":"UW","FMCGBEES.NS":"UW"},
    },
    "EARLY EXPANSION": {
        "score_range": (0.60, 0.80),
        "overweight":    ["Nifty Bank", "Nifty Metal", "Nifty Auto", "Nifty Infra", "Nifty Realty"],
        "neutral":       ["Nifty IT", "Nifty Energy", "Nifty PSU Bank"],
        "underweight":   ["Nifty FMCG", "Nifty Pharma", "Nifty Healthcare"],
        "action":        "Aggressively overweight cyclicals. Add mid/small caps in outperforming sectors.",
        "etfs":          {"BANKBEES.NS":"OW","ITBEES.NS":"N","PHARMABEES.NS":"UW",
                          "FMCGBEES.NS":"UW","METALBEES.NS":"OW","INFRABEES.NS":"OW"},
    },
    "MID CYCLE": {
        "score_range": (0.40, 0.60),
        "overweight":    ["Nifty Bank", "Nifty Auto", "Nifty IT", "Nifty Energy"],
        "neutral":       ["Nifty Metal", "Nifty Infra", "Nifty PSU Bank"],
        "underweight":   ["Nifty Realty", "Nifty Healthcare", "Nifty Utilities"],
        "action":        "Balanced allocation. Follow relative-strength signals monthly.",
        "etfs":          {"BANKBEES.NS":"OW","ITBEES.NS":"OW","PHARMABEES.NS":"N",
                          "FMCGBEES.NS":"N","METALBEES.NS":"N","INFRABEES.NS":"N"},
    },
    "LATE CYCLE": {
        "score_range": (0.20, 0.40),
        "overweight":    ["Nifty Energy", "Nifty FMCG", "Nifty Pharma", "Nifty IT"],
        "neutral":       ["Nifty Metal", "Nifty Infra", "Nifty Bank"],
        "underweight":   ["Nifty Realty", "Nifty Auto", "Nifty PSU Bank"],
        "action":        "Rotate defensive. Reduce beta. Tighten quality requirements.",
        "etfs":          {"BANKBEES.NS":"UW","ITBEES.NS":"OW","PHARMABEES.NS":"OW",
                          "FMCGBEES.NS":"OW","METALBEES.NS":"N","INFRABEES.NS":"UW"},
    },
    "CONTRACTION": {
        "score_range": (0.00, 0.20),
        "overweight":    ["Nifty FMCG", "Nifty Pharma", "Nifty Healthcare", "Nifty IT"],
        "neutral":       ["Nifty Energy"],
        "underweight":   ["Nifty Bank", "Nifty Realty", "Nifty Metal", "Nifty Auto", "Nifty Infra"],
        "action":        "Maximum defensive. Earnings visibility + inelastic demand + dividend yield.",
        "etfs":          {"BANKBEES.NS":"UW","ITBEES.NS":"OW","PHARMABEES.NS":"OW",
                          "FMCGBEES.NS":"OW","METALBEES.NS":"UW","GOLDBEES.NS":"OW"},
    },
}

# ── Scheduling ────────────────────────────────────────────────
SCHEDULE_DAY    = "monday"   # Run every Monday
SCHEDULE_TIME   = "08:00"    # 8:00 AM
