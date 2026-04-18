#!/usr/bin/env python3
# ============================================================
#  run_macro_cycle_ci.py
#  GitHub Actions headless runner.
#  Differences from run_macro_cycle.py (local):
#    • No Excel file — scores computed locally in Python
#    • No win32com — no visual refresh needed
#    • No interactive prompts — manual values from JSON file
#    • No colorama terminal colours
#    • Outputs written to output/ folder for artifact upload
#    • History written to history/ folder (committed back to repo)
#    • Email credentials read from environment variables (GitHub Secrets)
# ============================================================

import os
import sys
import json
import logging
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))

# ── Output paths (all CI artifacts go here) ──────────────────
OUTPUT_DIR  = Path("output")
HISTORY_DIR = Path("history")
OUTPUT_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

LOG_FILE        = OUTPUT_DIR / "macro_run.log"
SNAPSHOT_FILE   = OUTPUT_DIR / "macro_snapshot.json"
EMAIL_HTML_FILE = OUTPUT_DIR / "email_report.html"
HISTORY_FILE    = HISTORY_DIR / "macro_history.csv"
MANUAL_INPUT_FILE = Path("manual_inputs") / "weekly_inputs.json"

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("macro_cycle")

# ── Email config from GitHub Secrets (env vars) ──────────────
GMAIL_USER      = os.environ.get("GMAIL_USER", "")
GMAIL_PASS      = os.environ.get("GMAIL_PASS", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
DRY_RUN         = os.environ.get("DRY_RUN", "false").lower() == "true"
SKIP_EMAIL      = os.environ.get("SKIP_EMAIL", "false").lower() == "true"


# ════════════════════════════════════════════════════════════
#  STEP 1 — Load manual inputs from JSON file
# ════════════════════════════════════════════════════════════
def load_manual_inputs() -> dict:
    logger.info("Loading manual inputs from manual_inputs/weekly_inputs.json")
    if not MANUAL_INPUT_FILE.exists():
        logger.error(f"Manual input file not found: {MANUAL_INPUT_FILE}")
        sys.exit(1)

    data = json.loads(MANUAL_INPUT_FILE.read_text())
    result = {}
    required = ["pmi_manufacturing", "housing_starts", "earnings_growth", "unemployment_rate", "credit_growth", "bank_npa_ratio"]

    for key in required:
        item = data.get(key, {})
        val  = item.get("value")
        if val is None or val == "":
            logger.error(f"Manual input missing: {key} — edit manual_inputs/weekly_inputs.json")
            sys.exit(1)
        result[key] = str(val)
        logger.info(f"  Manual input [{key}]: {val}")

    return result


# ════════════════════════════════════════════════════════════
#  STEP 2 — Fetch all 15 indicators (no interactive prompts)
# ════════════════════════════════════════════════════════════
def fetch_indicators(manual_values: dict) -> dict:
    from src.macro_fetcher import (
        fetch_nifty_6m_change, fetch_pmi_manufacturing, fetch_repo_rate_trend,
        fetch_credit_growth, fetch_housing_starts, fetch_gdp_growth,
        fetch_iip_growth, fetch_earnings_growth, fetch_auto_sales,
        fetch_gst_collections, fetch_cpi_inflation, fetch_unemployment,
        fetch_bank_npa, fetch_current_account_deficit, fetch_wpi_inflation,
    )

    fetch_fns = [
        ("nifty_6m_change",         fetch_nifty_6m_change),
        ("pmi_manufacturing",       lambda: fetch_pmi_manufacturing(manual_values.get("pmi_manufacturing"))),
        ("repo_rate_trend",         fetch_repo_rate_trend),
        ("credit_growth",           lambda: fetch_credit_growth(manual_values.get("credit_growth"))),
        ("housing_starts",          lambda: fetch_housing_starts(manual_values.get("housing_starts"))),
        ("gdp_growth",              fetch_gdp_growth),
        ("iip_growth",              fetch_iip_growth),
        ("earnings_growth",         lambda: fetch_earnings_growth(manual_values.get("earnings_growth"))),
        ("auto_sales",              fetch_auto_sales),
        ("gst_collections",         fetch_gst_collections),
        ("cpi_inflation",           fetch_cpi_inflation),
        ("unemployment_rate",       lambda: fetch_unemployment(manual_values.get("unemployment_rate"))),
        ("bank_npa_ratio",          lambda: fetch_bank_npa(manual_values.get("bank_npa_ratio"))),
        ("current_account_deficit", fetch_current_account_deficit),
        ("wpi_inflation",           fetch_wpi_inflation),
    ]

    indicators = {}
    for key, fn in fetch_fns:
        logger.info(f"  Fetching [{key}]...")
        try:
            indicators[key] = fn()
        except Exception as e:
            logger.error(f"  ERROR fetching {key}: {e}")
            indicators[key] = {
                "key": key, "name": key, "value": None,
                "fetch_status": "MANUAL_REQUIRED", "is_live": False,
                "is_estimated": False, "source": "fetch_error",
                "notes": str(e), "data_date": "", "source_url": "",
                "fetch_time": datetime.datetime.now().isoformat(),
            }

    live   = sum(1 for v in indicators.values() if v.get("fetch_status") == "OK" and not v.get("is_estimated"))
    est    = sum(1 for v in indicators.values() if v.get("is_estimated"))
    manual = sum(1 for v in indicators.values() if v.get("fetch_status") == "MANUAL_REQUIRED")
    logger.info(f"Fetch complete: {live} live | {est} estimated | {manual} manual")
    return indicators


# ════════════════════════════════════════════════════════════
#  STEP 3 — Compute composite score locally (no Excel in CI)
# ════════════════════════════════════════════════════════════
WEIGHTS = {
    "nifty_6m_change":        0.10,
    "pmi_manufacturing":      0.10,
    "repo_rate_trend":        0.10,
    "credit_growth":          0.10,
    "housing_starts":         0.10,
    "gdp_growth":             0.067,
    "iip_growth":             0.067,
    "earnings_growth":        0.067,
    "auto_sales":             0.067,
    "gst_collections":        0.067,
    "cpi_inflation":          0.033,
    "unemployment_rate":      0.033,
    "bank_npa_ratio":         0.033,
    "current_account_deficit":0.033,
    "wpi_inflation":          0.033,
}

def classify_signal(key: str, value_str: str) -> str:
    """Replicate Excel IF formulas — same thresholds as cells C/D/E in the sheet."""
    import re
    THRESHOLDS = {
        "nifty_6m_change":         lambda v: "Bullish" if v > 10   else "Neutral" if v >= 0  else "Bearish",
        "pmi_manufacturing":       lambda v: "Bullish" if v > 55   else "Neutral" if v >= 50 else "Bearish",
        "repo_rate_trend":         lambda v: "Bullish" if v < 0    else "Neutral" if v == 0  else "Bearish",
        "credit_growth":           lambda v: "Bullish" if v > 15   else "Neutral" if v >= 8  else "Bearish",
        "housing_starts":          lambda v: "Bullish" if v == 1   else "Neutral" if v == 0  else "Bearish",
        "gdp_growth":              lambda v: "Bullish" if v > 7    else "Neutral" if v >= 5  else "Bearish",
        "iip_growth":              lambda v: "Bullish" if v > 8    else "Neutral" if v >= 3  else "Bearish",
        "earnings_growth":         lambda v: "Bullish" if v > 15   else "Neutral" if v >= 8  else "Bearish",
        "auto_sales":              lambda v: "Bullish" if v > 15   else "Neutral" if v >= 5  else "Bearish",
        "gst_collections":         lambda v: "Bullish" if v > 12   else "Neutral" if v >= 6  else "Bearish",
        "cpi_inflation":           lambda v: "Bullish" if v < 4    else "Neutral" if v < 6   else "Bearish",
        "unemployment_rate":       lambda v: "Bullish" if v < 6    else "Neutral" if v < 8   else "Bearish",
        "bank_npa_ratio":          lambda v: "Bullish" if v < 3    else "Neutral" if v < 6   else "Bearish",
        "current_account_deficit": lambda v: "Bullish" if abs(v) < 2 else "Neutral" if abs(v) < 3 else "Bearish",
        "wpi_inflation":           lambda v: "Bullish" if v < 3    else "Neutral" if v < 6   else "Bearish",
    }
    try:
        if key == "housing_starts":
            v = 1 if "rising" in str(value_str).lower() else (-1 if "falling" in str(value_str).lower() else 0)
        elif key == "repo_rate_trend":
            m = re.search(r"([+-]?\d+)", str(value_str))
            v = float(m.group(1)) if m else 0.0
        else:
            m = re.search(r"-?\d+\.?\d*", str(value_str))
            v = float(m.group()) if m else 0.0
        return THRESHOLDS[key](v)
    except Exception:
        return "Neutral"

def compute_score_locally(indicators: dict) -> dict:
    score    = 0.0
    breakdown = {}
    for key, weight in WEIGHTS.items():
        ind    = indicators.get(key, {})
        val    = ind.get("value")
        signal = classify_signal(key, str(val)) if val is not None else "Neutral"
        s      = 1.0 if signal == "Bullish" else 0.5 if signal == "Neutral" else 0.0
        ws     = round(s * weight, 5)
        score += ws
        breakdown[key] = {"signal": signal, "score": s, "weight": weight, "weighted_score": ws}

    score = round(score, 6)

    if   score >= 0.80: phase = "STRONG RECOVERY"
    elif score >= 0.60: phase = "EARLY EXPANSION"
    elif score >= 0.40: phase = "MID CYCLE"
    elif score >= 0.20: phase = "LATE CYCLE"
    else:               phase = "CONTRACTION"

    logger.info(f"Composite score: {score:.4f} → Phase: {phase}")
    return {"composite_score": score, "phase": phase, "breakdown": breakdown}


# ════════════════════════════════════════════════════════════
#  STEP 4 — Momentum vs prior week
# ════════════════════════════════════════════════════════════
def compute_momentum(score: float) -> dict:
    from src.history_tracker import load_history
    history = load_history(HISTORY_FILE, weeks=2)
    if len(history) >= 1:
        try:
            prior_score = float(history[-1].get("composite_score", score))
            prior_phase = history[-1].get("phase", "")
            delta       = round(score - prior_score, 4)
            momentum    = "Rising" if delta > 0.02 else "Falling" if delta < -0.02 else "Stable"
            return {"prior_score": prior_score, "prior_phase": prior_phase,
                    "score_delta": delta, "momentum": momentum}
        except Exception:
            pass
    return {"prior_score": None, "prior_phase": None,
            "score_delta": None, "momentum": "First Run"}


# ════════════════════════════════════════════════════════════
#  STEP 5 — Sector recommendations + ETF data
# ════════════════════════════════════════════════════════════
def get_sector_recs(phase: str) -> dict:
    from src.sector_mapper import get_sector_recommendations
    logger.info(f"Fetching sector recommendations for phase: {phase}")
    return get_sector_recommendations(phase)


# ════════════════════════════════════════════════════════════
#  STEP 6 — Build cycle_result dict
# ════════════════════════════════════════════════════════════
def build_cycle_result(score_data: dict, momentum_data: dict,
                       indicators: dict, run_date: str) -> dict:
    score  = score_data["composite_score"]
    phase  = score_data["phase"]
    live   = sum(1 for v in indicators.values() if v.get("fetch_status") == "OK" and not v.get("is_estimated"))
    est    = sum(1 for v in indicators.values() if v.get("is_estimated"))
    manual = sum(1 for v in indicators.values() if v.get("fetch_status") == "MANUAL_REQUIRED")

    if live >= 12:   confidence = "High"
    elif live >= 9:  confidence = "Medium"
    else:            confidence = "Low"

    prior_phase   = momentum_data.get("prior_phase")
    phase_changed = (prior_phase is not None and prior_phase != "" and prior_phase != phase)
    delta         = momentum_data.get("score_delta")
    rebalance     = phase_changed or (delta is not None and abs(delta) > 0.05)

    return {
        "composite_score":  score,
        "phase":            phase,
        "score_breakdown":  score_data.get("breakdown", {}),
        "prior_score":      momentum_data.get("prior_score"),
        "score_delta":      delta,
        "momentum":         momentum_data.get("momentum", "—"),
        "prior_phase":      prior_phase,
        "phase_changed":    phase_changed,
        "confidence":       confidence,
        "live_count":       live,
        "estimated_count":  est,
        "manual_count":     manual,
        "rebalance_flag":   rebalance,
        "run_date":         run_date,
    }


# ════════════════════════════════════════════════════════════
#  STEP 7 — Send email
# ════════════════════════════════════════════════════════════
def send_report(cycle_result: dict, indicators: dict, sector_recs: dict) -> None:
    from src.report_sender import build_html_email, send_email

    run_date = datetime.datetime.now().strftime("%d %b %Y %H:%M")
    html     = build_html_email(cycle_result, indicators, sector_recs, run_date)

    # Always save HTML for artifact upload
    EMAIL_HTML_FILE.write_text(html, encoding="utf-8")
    logger.info(f"HTML report saved: {EMAIL_HTML_FILE}")

    if SKIP_EMAIL:
        logger.info("SKIP_EMAIL=true — email not sent")
        return

    if not GMAIL_USER or not GMAIL_PASS or not RECIPIENT_EMAIL:
        logger.error("Email credentials missing — set GMAIL_USER / GMAIL_PASS / RECIPIENT_EMAIL in GitHub Secrets")
        return

    logger.info(f"Sending email to {RECIPIENT_EMAIL}...")
    ok = send_email(html, cycle_result, GMAIL_USER, GMAIL_PASS, RECIPIENT_EMAIL)
    if ok:
        logger.info("✅ Email sent successfully")
    else:
        logger.error("❌ Email send failed — check logs")


# ════════════════════════════════════════════════════════════
#  STEP 8 — Save history and snapshot
# ════════════════════════════════════════════════════════════
def save_outputs(indicators: dict, cycle_result: dict, sector_recs: dict) -> None:
    from src.history_tracker import save_to_history

    if not DRY_RUN:
        save_to_history(HISTORY_FILE, indicators, cycle_result)
        logger.info(f"History saved: {HISTORY_FILE}")
    else:
        logger.info("DRY_RUN=true — history not saved")

    snapshot = {
        "run_date":     cycle_result["run_date"],
        "indicators":   indicators,
        "cycle_result": cycle_result,
        "sector_recs":  sector_recs,
    }
    SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    logger.info(f"Snapshot saved: {SNAPSHOT_FILE}")


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
def main() -> None:
    run_date = datetime.datetime.now().strftime("%d-%b-%Y %H:%M UTC")
    logger.info("=" * 60)
    logger.info(f"INDIA MACRO CYCLE SYSTEM — CI RUN — {run_date}")
    logger.info(f"DRY_RUN={DRY_RUN} | SKIP_EMAIL={SKIP_EMAIL}")
    logger.info("=" * 60)

    # 1. Load manual inputs
    manual_values = load_manual_inputs()

    # 2. Fetch all 15 indicators
    logger.info("Fetching all 15 indicators...")
    indicators = fetch_indicators(manual_values)

    # 3. Compute composite score
    logger.info("Computing composite score...")
    score_data = compute_score_locally(indicators)

    # 4. Momentum
    momentum_data = compute_momentum(score_data["composite_score"])
    logger.info(f"Momentum: {momentum_data['momentum']} (Δ {momentum_data.get('score_delta')})")

    # 5. Sector recs
    sector_recs = get_sector_recs(score_data["phase"])

    # 6. Build result
    cycle_result = build_cycle_result(score_data, momentum_data, indicators, run_date)

    # 7. Email
    send_report(cycle_result, indicators, sector_recs)

    # 8. Save
    save_outputs(indicators, cycle_result, sector_recs)

    # 9. Print summary to logs
    logger.info("=" * 60)
    logger.info(f"CYCLE PHASE  : {cycle_result['phase']}")
    logger.info(f"SCORE        : {cycle_result['composite_score']:.4f}")
    logger.info(f"MOMENTUM     : {cycle_result['momentum']}")
    logger.info(f"CONFIDENCE   : {cycle_result['confidence']}")
    logger.info(f"REBALANCE    : {cycle_result['rebalance_flag']}")
    logger.info("=" * 60)
    logger.info("CI RUN COMPLETE")


if __name__ == "__main__":
    main()
