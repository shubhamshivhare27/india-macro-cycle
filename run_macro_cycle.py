#!/usr/bin/env python3
# ============================================================
#  run_macro_cycle.py  — MAIN ORCHESTRATOR
#  Run this every Monday morning:
#    python run_macro_cycle.py
#
#  Optional flags:
#    --no-email    Skip email prompt
#    --dry-run     Show review but don't update Excel
#    --history     Show last 4 weeks history and exit
#    --schedule    Install Windows Task Scheduler job
# ============================================================

import sys
import json
import logging
import argparse
import datetime
from pathlib import Path

# ── Ensure src/ is on path ────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))

from colorama import Fore, Style, init as colorama_init
colorama_init(autoreset=True)

# ── Config ────────────────────────────────────────────────────
from config import (
    EXCEL_PATH, EXCEL_SHEET, GMAIL_USER, GMAIL_PASS, RECIPIENT_EMAIL,
    GSHEET_CSV_URL, DATA_DIR, LOGS_DIR, DASHBOARD_DIR,
    SNAPSHOT_FILE, HISTORY_FILE, LOG_FILE,
)

# ── Ensure directories exist ─────────────────────────────────
for d in [DATA_DIR, LOGS_DIR, DASHBOARD_DIR]:
    d.mkdir(parents=True, exist_ok=True)

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

# ── Imports ───────────────────────────────────────────────────
from src.gsheet_reader   import get_gsheet_and_prompt
from src.macro_fetcher   import fetch_all_indicators
from src.input_review    import show_review_table, prompt_action
from src.excel_updater   import update_excel
from src.cycle_reader    import compute_cycle_result, print_cycle_result
from src.sector_mapper   import get_sector_recommendations, print_sector_table
from src.history_tracker import save_to_history, print_history_table
from src.report_sender   import preview_and_send


# ════════════════════════════════════════════════════════════
def print_banner(run_date: str) -> None:
    W = 80
    print()
    print(Fore.CYAN + Style.BRIGHT + "╔" + "═"*(W-2) + "╗")
    print(Fore.CYAN + Style.BRIGHT + "║" + " "*((W-2-36)//2) + "INDIA MACRO CYCLE SYSTEM — v1.0" + " "*((W-2-36+1)//2) + "║")
    print(Fore.CYAN + Style.BRIGHT + "║" + f"  Run Date: {run_date}".ljust(W-2) + "║")
    print(Fore.CYAN + Style.BRIGHT + "║" + "  Merrill Lynch Investment Clock — Adapted for India".ljust(W-2) + "║")
    print(Fore.CYAN + Style.BRIGHT + "╚" + "═"*(W-2) + "╝" + Style.RESET_ALL)
    print()


def print_paywall_notice() -> None:
    print()
    print(Fore.YELLOW + Style.BRIGHT + "  ⚠  PAYWALL / MANUAL INDICATORS" + Style.RESET_ALL)
    print(f"  {'─'*65}")
    print("  The following indicators CANNOT be fetched automatically:")
    print()
    print(f"  {'#':<4} {'Indicator':<35} {'Reason':<30}")
    print(f"  {'─'*4} {'─'*35} {'─'*30}")
    manual_items = [
        ("1", "PMI Manufacturing",          "S&P Global India PMI — paywalled"),
        ("2", "Housing Starts",             "No official real-time API"),
        ("3", "Corporate Earnings Growth",  "NSE earnings — no free API"),
        ("4", "Unemployment Rate",          "CMIE — paywalled"),
    ]
    for num, name, reason in manual_items:
        print(f"  {num:<4} {name:<35} {reason}")
    print()
    print("  HOW TO ENTER THESE:")
    print("  1. Open your Google Sheet (URL configured in config.py)")
    print("  2. Enter values in two columns: Indicator_Key | Value")
    print("  3. Example rows:")
    print("       pmi_manufacturing   | 56.4")
    print("       housing_starts      | Rising")
    print("       earnings_growth     | 18.5")
    print("       unemployment_rate   | 7.8")
    print("  4. Python will read them automatically, or prompt you here if missing.")
    print(f"  {'─'*65}")
    print()


def install_scheduler() -> None:
    """Install Windows Task Scheduler entry to run every Monday 8AM."""
    import subprocess, os
    script_path = Path(__file__).resolve()
    python_path = sys.executable
    task_name   = "IndiaMacroCycleSystem"
    cmd = (
        f'schtasks /create /f /tn "{task_name}" '
        f'/tr "\\"{python_path}\\" \\"{script_path}\\" --no-email" '
        f'/sc WEEKLY /d MON /st 08:00 /rl HIGHEST'
    )
    print(f"  Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(Fore.GREEN + f"  ✅ Scheduled task '{task_name}' created — runs every Monday at 08:00." + Style.RESET_ALL)
    else:
        print(Fore.RED + f"  ❌ Scheduler setup failed: {result.stderr}" + Style.RESET_ALL)
        print("  Try running as Administrator.")


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(description="India Macro Cycle System")
    parser.add_argument("--no-email",  action="store_true", help="Skip email prompt")
    parser.add_argument("--dry-run",   action="store_true", help="Show review but don't update Excel")
    parser.add_argument("--history",   action="store_true", help="Show 4-week history and exit")
    parser.add_argument("--schedule",  action="store_true", help="Install Windows Task Scheduler")
    args = parser.parse_args()

    run_date = datetime.datetime.now().strftime("%d-%b-%Y %H:%M")

    # ── Show history only ─────────────────────────────────────
    if args.history:
        print_banner(run_date)
        print_history_table(HISTORY_FILE, weeks=4)
        return

    # ── Install scheduler ─────────────────────────────────────
    if args.schedule:
        install_scheduler()
        return

    print_banner(run_date)
    logger.info(f"=== INDIA MACRO CYCLE SYSTEM RUN — {run_date} ===")

    # ── STEP 0: Paywall notice ────────────────────────────────
    print_paywall_notice()

    # ── STEP 1: Read Google Sheet + prompt for missing ────────
    print(Fore.CYAN + "  [1/9] Reading Google Sheet for manual indicators..." + Style.RESET_ALL)
    gsheet_values = get_gsheet_and_prompt(GSHEET_CSV_URL)
    print(Fore.GREEN + f"  ✅ Google Sheet: {len(gsheet_values)} values loaded." + Style.RESET_ALL)
    print()

    # ── STEP 2: Fetch all 15 indicators ──────────────────────
    print(Fore.CYAN + "  [2/9] Fetching all 15 macro indicators from official sources..." + Style.RESET_ALL)
    print("  (This may take 30-60 seconds — multiple sources are checked)")
    print()

    try:
        from tqdm import tqdm
        indicators = {}
        fetcher_names = [
            "Nifty 6M Change","PMI Manufacturing","Repo Rate Trend","Credit Growth","Housing Starts",
            "GDP Growth","IIP Growth","Earnings Growth","Auto Sales","GST Collections",
            "CPI Inflation","Unemployment Rate","Bank NPA Ratio","Current Account Deficit","WPI Inflation",
        ]
        from src.macro_fetcher import (
            fetch_nifty_6m_change, fetch_pmi_manufacturing, fetch_repo_rate_trend,
            fetch_credit_growth, fetch_housing_starts, fetch_gdp_growth,
            fetch_iip_growth, fetch_earnings_growth, fetch_auto_sales,
            fetch_gst_collections, fetch_cpi_inflation, fetch_unemployment,
            fetch_bank_npa, fetch_current_account_deficit, fetch_wpi_inflation,
        )
        fetch_fns = [
            ("nifty_6m_change",         fetch_nifty_6m_change),
            ("pmi_manufacturing",       lambda: fetch_pmi_manufacturing(gsheet_values.get("pmi_manufacturing"))),
            ("repo_rate_trend",         fetch_repo_rate_trend),
            ("credit_growth",           fetch_credit_growth),
            ("housing_starts",          lambda: fetch_housing_starts(gsheet_values.get("housing_starts"))),
            ("gdp_growth",              fetch_gdp_growth),
            ("iip_growth",              fetch_iip_growth),
            ("earnings_growth",         lambda: fetch_earnings_growth(gsheet_values.get("earnings_growth"))),
            ("auto_sales",              fetch_auto_sales),
            ("gst_collections",         fetch_gst_collections),
            ("cpi_inflation",           fetch_cpi_inflation),
            ("unemployment_rate",       lambda: fetch_unemployment(gsheet_values.get("unemployment_rate"))),
            ("bank_npa",          fetch_bank_npa),
            ("current_account_deficit", fetch_current_account_deficit),
            ("wpi_inflation",           fetch_wpi_inflation),
        ]
        with tqdm(fetch_fns, desc="  Fetching", ncols=70) as pbar:
            for key, fn in pbar:
                pbar.set_postfix_str(key)
                indicators[key] = fn()
    except ImportError:
        from src.macro_fetcher import fetch_all_indicators
        indicators = fetch_all_indicators(gsheet_values)

    print()
    print(Fore.GREEN + f"  ✅ Fetch complete." + Style.RESET_ALL)
    print()

    # ── STEP 3: Transparency review (MANDATORY) ──────────────
    print(Fore.CYAN + "  [3/9] TRANSPARENCY REVIEW — Review all values before Excel update" + Style.RESET_ALL)
    show_review_table(indicators, run_date)
    indicators = prompt_action(indicators)   # user must confirm

    # ── STEP 4: Show prior-week history ───────────────────────
    print(Fore.CYAN + "  [4/9] Prior week comparison..." + Style.RESET_ALL)
    print_history_table(HISTORY_FILE, weeks=3)

    # ── STEP 5: Update Excel ──────────────────────────────────
    if args.dry_run:
        print(Fore.YELLOW + "  [5/9] DRY RUN — Skipping Excel update." + Style.RESET_ALL)
        print()
    else:
        print(Fore.CYAN + "  [5/9] Updating Excel file..." + Style.RESET_ALL)
        if not EXCEL_PATH.exists():
            print(Fore.RED + f"  ❌ Excel file not found: {EXCEL_PATH}" + Style.RESET_ALL)
            print("  Please update EXCEL_PATH in config.py with the correct path.")
            logger.error(f"Excel not found: {EXCEL_PATH}")
        else:
            write_log = update_excel(EXCEL_PATH, indicators, EXCEL_SHEET)
            logger.info(f"  Excel updated: {len(write_log)} cells written")
        print()

    # ── STEP 6: Read cycle phase from Excel ──────────────────
    print(Fore.CYAN + "  [6/9] Reading cycle phase from Excel..." + Style.RESET_ALL)
    if not args.dry_run and EXCEL_PATH.exists():
        cycle_result = compute_cycle_result(EXCEL_PATH, EXCEL_SHEET, HISTORY_FILE, indicators)
    else:
        # Dry-run: compute locally
        from src.cycle_reader import _score_to_phase
        score = 0.0
        from src.input_review import classify_signal
        WEIGHTS = {"nifty_6m_change":0.10,"pmi_manufacturing":0.10,"repo_rate_trend":0.10,
                   "credit_growth":0.10,"housing_starts":0.10,"gdp_growth":0.067,
                   "iip_growth":0.067,"earnings_growth":0.067,"auto_sales":0.067,
                   "gst_collections":0.067,"cpi_inflation":0.033,"unemployment_rate":0.033,
                   "bank_npa":0.033,"current_account_deficit":0.033,"wpi_inflation":0.033}
        for k, w in WEIGHTS.items():
            sig = classify_signal(k, str(indicators.get(k,{}).get("value","")))
            score += w * (1.0 if sig == "Bullish" else 0.5 if sig == "Neutral" else 0.0)
        cycle_result = {
            "composite_score": round(score, 4),
            "phase": _score_to_phase(score),
            "momentum": "N/A", "score_delta": None, "prior_phase": None,
            "phase_changed": False, "confidence": "N/A",
            "live_count": sum(1 for v in indicators.values() if v.get("fetch_status")=="OK"),
            "estimated_count": sum(1 for v in indicators.values() if v.get("is_estimated")),
            "manual_count": sum(1 for v in indicators.values() if v.get("fetch_status")=="MANUAL_REQUIRED"),
            "rebalance_flag": False, "run_date": run_date,
        }

    print_cycle_result(cycle_result)

    # ── STEP 7: Sector recommendations ───────────────────────
    print(Fore.CYAN + "  [7/9] Fetching ETF data and generating sector recommendations..." + Style.RESET_ALL)
    sector_recs = get_sector_recommendations(cycle_result["phase"])
    print_sector_table(sector_recs)

    # ── STEP 8: Save history ──────────────────────────────────
    print(Fore.CYAN + "  [8/9] Saving to history..." + Style.RESET_ALL)
    save_to_history(HISTORY_FILE, indicators, cycle_result)

    # Save full snapshot
    snapshot = {
        "run_date":    run_date,
        "indicators":  indicators,
        "cycle_result":cycle_result,
        "sector_recs": sector_recs,
    }
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, default=str)
    logger.info(f"  Snapshot saved: {SNAPSHOT_FILE}")

    # ── STEP 9: Email report ──────────────────────────────────
    if not args.no_email:
        print(Fore.CYAN + "  [9/9] Email report..." + Style.RESET_ALL)
        preview_path = DASHBOARD_DIR / "email_preview.html"
        preview_and_send(
            cycle_result, indicators, sector_recs,
            GMAIL_USER, GMAIL_PASS, RECIPIENT_EMAIL,
            preview_path=preview_path,
        )
    else:
        print(Fore.YELLOW + "  [9/9] Email skipped (--no-email flag)." + Style.RESET_ALL)
        # Still save HTML preview
        from src.report_sender import build_html_email
        html = build_html_email(cycle_result, indicators, sector_recs)
        preview_path = DASHBOARD_DIR / "email_preview.html"
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  HTML report saved: {preview_path}")

    # ── Done ──────────────────────────────────────────────────
    print()
    print(Fore.GREEN + Style.BRIGHT + "  ✅ RUN COMPLETE" + Style.RESET_ALL)
    print(f"  Excel:    {EXCEL_PATH}")
    print(f"  History:  {HISTORY_FILE}")
    print(f"  Snapshot: {SNAPSHOT_FILE}")
    print(f"  Log:      {LOG_FILE}")
    print()
    print(f"  To view the dashboard: streamlit run dashboard/streamlit_dashboard.py")
    print()
    logger.info(f"=== RUN COMPLETE — {run_date} ===")


if __name__ == "__main__":
    main()
