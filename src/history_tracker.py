# ============================================================
#  src/history_tracker.py
#  Appends weekly run data to macro_history.csv.
#  Shows 4-week comparison table with sector changes.
# ============================================================

import csv
import logging
import datetime
from pathlib import Path

logger = logging.getLogger("macro_cycle")

HISTORY_COLS = [
    "date", "composite_score", "phase",
    "nifty_6m_change","pmi_manufacturing","repo_rate_trend","credit_growth","housing_starts",
    "gdp_growth","iip_growth","earnings_growth","auto_sales","gst_collections",
    "cpi_inflation","unemployment_rate","bank_npa_ratio","current_account_deficit","wpi_inflation",
    "live_count","estimated_count","manual_count","rebalance_flag",
]


def save_to_history(history_path: Path, indicators: dict, cycle_result: dict) -> None:
    """Append this week's run to macro_history.csv."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = history_path.exists()

    row = {
        "date":            cycle_result.get("run_date", datetime.datetime.now().strftime("%Y-%m-%d")),
        "composite_score": round(cycle_result.get("composite_score", 0), 4),
        "phase":           cycle_result.get("phase", ""),
        "live_count":      cycle_result.get("live_count", 0),
        "estimated_count": cycle_result.get("estimated_count", 0),
        "manual_count":    cycle_result.get("manual_count", 0),
        "rebalance_flag":  cycle_result.get("rebalance_flag", False),
    }
    for key in ["nifty_6m_change","pmi_manufacturing","repo_rate_trend","credit_growth","housing_starts",
                "gdp_growth","iip_growth","earnings_growth","auto_sales","gst_collections",
                "cpi_inflation","unemployment_rate","bank_npa_ratio","current_account_deficit","wpi_inflation"]:
        ind = indicators.get(key, {})
        row[key] = str(ind.get("value", "")) if ind else ""

    with open(history_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_COLS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    logger.info(f"  History saved: {history_path}")


def load_history(history_path: Path, weeks: int = 8) -> list[dict]:
    """Load last N weeks of history."""
    if not history_path.exists():
        return []
    try:
        rows = []
        with open(history_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows[-weeks:]
    except Exception as e:
        logger.error(f"  Could not load history: {e}")
        return []


def print_history_table(history_path: Path, weeks: int = 4) -> None:
    """Print prior-weeks comparison table."""
    from colorama import Fore, Style

    rows = load_history(history_path, weeks=weeks)
    if not rows:
        print(Fore.YELLOW + "  No history yet — this is the first run." + Style.RESET_ALL)
        return

    W = 90
    print()
    print(Fore.CYAN + Style.BRIGHT + "═" * W + Style.RESET_ALL)
    print(Fore.CYAN + Style.BRIGHT + f"  HISTORICAL COMPARISON — LAST {min(len(rows), weeks)} WEEK(S)" + Style.RESET_ALL)
    print(Fore.CYAN + Style.BRIGHT + "═" * W + Style.RESET_ALL)
    print()

    # Header
    date_cols = [r["date"][:10] for r in rows]
    header = f"  {'Indicator':<33}"
    for d in date_cols:
        header += f"  {d:<13}"
    print(header)
    print(f"  {'─'*33}" + "  " + "  ".join(["─"*13]*len(rows)))

    # Composite score row
    scores_row = f"  {'Composite Score':<33}"
    for r in rows:
        s = r.get("composite_score", "")
        scores_row += f"  {s:<13}"
    print(Fore.GREEN + scores_row + Style.RESET_ALL)

    # Phase row
    phase_row = f"  {'Phase':<33}"
    for r in rows:
        phase_row += f"  {r.get('phase','')[:13]:<13}"
    print(Fore.YELLOW + phase_row + Style.RESET_ALL)

    print()

    # Indicator rows
    IND_KEYS = [
        "nifty_6m_change","pmi_manufacturing","repo_rate_trend","credit_growth","housing_starts",
        "gdp_growth","iip_growth","earnings_growth","auto_sales","gst_collections",
        "cpi_inflation","unemployment_rate","bank_npa_ratio","current_account_deficit","wpi_inflation",
    ]
    LABELS = {
        "nifty_6m_change":        "Nifty 50 6M Change",
        "pmi_manufacturing":      "PMI Manufacturing",
        "repo_rate_trend":        "Repo Rate Trend",
        "credit_growth":          "Credit Growth YoY",
        "housing_starts":         "Housing Starts",
        "gdp_growth":             "GDP Growth",
        "iip_growth":             "IIP Growth",
        "earnings_growth":        "Earnings Growth",
        "auto_sales":             "Auto Sales",
        "gst_collections":        "GST Collections",
        "cpi_inflation":          "CPI Inflation",
        "unemployment_rate":      "Unemployment Rate",
        "bank_npa_ratio":         "Bank NPA Ratio",
        "current_account_deficit":"Current A/C Deficit",
        "wpi_inflation":          "WPI Inflation",
    }
    for key in IND_KEYS:
        row_str = f"  {LABELS.get(key,key):<33}"
        for r in rows:
            row_str += f"  {str(r.get(key,'—'))[:13]:<13}"
        print(row_str)

    print()
    print(f"  {'─'*W}")

    # Change summary (last week vs week before last)
    if len(rows) >= 2:
        curr = rows[-1]
        prev = rows[-2]
        print(Fore.CYAN + "  WEEK-ON-WEEK CHANGES:" + Style.RESET_ALL)
        try:
            score_chg = float(curr.get("composite_score",0)) - float(prev.get("composite_score",0))
            colour = Fore.GREEN if score_chg > 0 else Fore.RED if score_chg < 0 else Fore.YELLOW
            print(colour + f"  Composite Score: {score_chg:+.4f}" + Style.RESET_ALL)
        except Exception:
            pass
        if curr.get("phase") != prev.get("phase"):
            print(Fore.YELLOW + f"  Phase: {prev.get('phase')} → {curr.get('phase')} ⚠ PHASE CHANGE" + Style.RESET_ALL)
        else:
            print(f"  Phase: {curr.get('phase')} (unchanged)")
    print()
