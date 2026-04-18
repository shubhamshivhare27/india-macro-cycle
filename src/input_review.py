# ============================================================
#  src/input_review.py
#  Mandatory transparency review screen.
#  Shows EVERY value, source, date, quality flag BEFORE
#  anything is written to Excel.
#  User must actively confirm — cannot be skipped.
# ============================================================

import datetime
import logging
from colorama import Fore, Back, Style, init

init(autoreset=True)
logger = logging.getLogger("macro_cycle")

# ── Signal classification (mirrors Excel formulas) ───────────
def classify_signal(key: str, value_str: str) -> str:
    """Return Bullish / Neutral / Bearish using same thresholds as Excel."""
    THRESHOLDS = {
        "nifty_6m_change":         (lambda v: "Bullish" if v > 10 else "Neutral" if v >= 0 else "Bearish"),
        "pmi_manufacturing":       (lambda v: "Bullish" if v > 55 else "Neutral" if v >= 50 else "Bearish"),
        "repo_rate_trend":         (lambda v: "Bullish" if v < 0 else "Neutral" if v == 0 else "Bearish"),
        "credit_growth":           (lambda v: "Bullish" if v > 15 else "Neutral" if v >= 8 else "Bearish"),
        "housing_starts":          (lambda v: "Bullish" if v == 1 else "Neutral" if v == 0 else "Bearish"),
        "gdp_growth":              (lambda v: "Bullish" if v > 7 else "Neutral" if v >= 5 else "Bearish"),
        "iip_growth":              (lambda v: "Bullish" if v > 8 else "Neutral" if v >= 3 else "Bearish"),
        "earnings_growth":         (lambda v: "Bullish" if v > 15 else "Neutral" if v >= 8 else "Bearish"),
        "auto_sales":              (lambda v: "Bullish" if v > 15 else "Neutral" if v >= 5 else "Bearish"),
        "gst_collections":         (lambda v: "Bullish" if v > 12 else "Neutral" if v >= 6 else "Bearish"),
        "cpi_inflation":           (lambda v: "Bullish" if v < 4 else "Neutral" if v < 6 else "Bearish"),
        "unemployment_rate":       (lambda v: "Bullish" if v < 6 else "Neutral" if v < 8 else "Bearish"),
        "bank_npa_ratio":          (lambda v: "Bullish" if v < 3 else "Neutral" if v < 6 else "Bearish"),
        "current_account_deficit": (lambda v: "Bullish" if abs(v) < 2 else "Neutral" if abs(v) < 3 else "Bearish"),
        "wpi_inflation":           (lambda v: "Bullish" if v < 3 else "Neutral" if v < 6 else "Bearish"),
    }
    try:
        if key == "housing_starts":
            v = 1 if "rising" in value_str.lower() else (-1 if "falling" in value_str.lower() else 0)
        elif key == "repo_rate_trend":
            import re
            m = re.search(r"([+-]?\d+)", str(value_str))
            v = float(m.group(1)) if m else 0
        else:
            import re
            m = re.search(r"-?\d+\.?\d*", str(value_str))
            v = float(m.group()) if m else 0
        return THRESHOLDS[key](v)
    except Exception:
        return "Unknown"

def _sig_colour(signal: str) -> str:
    if signal == "Bullish":  return Fore.GREEN  + "🟢 Bullish"  + Style.RESET_ALL
    if signal == "Neutral":  return Fore.YELLOW + "🟡 Neutral"  + Style.RESET_ALL
    if signal == "Bearish":  return Fore.RED    + "🔴 Bearish"  + Style.RESET_ALL
    return Fore.WHITE + "⚪ Unknown" + Style.RESET_ALL

def _status_colour(status: str) -> str:
    if status == "OK":              return Fore.GREEN  + "✅ LIVE"      + Style.RESET_ALL
    if status == "ESTIMATED":       return Fore.YELLOW + "⚠  ESTIMATED" + Style.RESET_ALL
    if status == "MANUAL_REQUIRED": return Fore.RED    + "❌ MANUAL"    + Style.RESET_ALL
    return Fore.WHITE + status + Style.RESET_ALL

GROUP_HEADERS = {
    "nifty_6m_change":         "── LEADING INDICATORS (Weight: 10% each | Group: 50%) ──",
    "gdp_growth":              "── COINCIDENT INDICATORS (Weight: 6.7% each | Group: 33%) ──",
    "cpi_inflation":           "── LAGGING INDICATORS (Weight: 3.3% each | Group: 17%) ──",
}

ORDER = [
    "nifty_6m_change","pmi_manufacturing","repo_rate_trend","credit_growth","housing_starts",
    "gdp_growth","iip_growth","earnings_growth","auto_sales","gst_collections",
    "cpi_inflation","unemployment_rate","bank_npa_ratio","current_account_deficit","wpi_inflation",
]

LABELS = {
    "nifty_6m_change":        "Nifty 50 6M Price Change",
    "pmi_manufacturing":      "PMI Manufacturing",
    "repo_rate_trend":        "RBI Repo Rate Trend (3M)",
    "credit_growth":          "Credit Growth YoY",
    "housing_starts":         "Housing Starts",
    "gdp_growth":             "GDP Growth QoQ Ann.",
    "iip_growth":             "IIP Industrial Prod. YoY",
    "earnings_growth":        "Corporate Earnings Growth",
    "auto_sales":             "Auto Sales YoY",
    "gst_collections":        "GST Collections YoY",
    "cpi_inflation":          "CPI Inflation",
    "unemployment_rate":      "Unemployment Rate",
    "bank_npa_ratio":         "Bank NPA Ratio",
    "current_account_deficit":"Current Account Deficit",
    "wpi_inflation":          "WPI Inflation",
}

def show_review_table(indicators: dict, run_date: str = None) -> None:
    """Print the full transparency review table to console."""
    if run_date is None:
        run_date = datetime.datetime.now().strftime("%d-%b-%Y %H:%M")

    W = 90
    print()
    print(Fore.CYAN + Style.BRIGHT + "═" * W)
    print(Fore.CYAN + Style.BRIGHT + f"  INDIA MACRO INPUT REVIEW — {run_date}")
    print(Fore.CYAN + Style.BRIGHT + "  Review ALL values carefully before they are written to Excel.")
    print(Fore.CYAN + Style.BRIGHT + "═" * W + Style.RESET_ALL)
    print()

    live_count    = sum(1 for v in indicators.values() if v["fetch_status"] == "OK")
    est_count     = sum(1 for v in indicators.values() if v["fetch_status"] == "ESTIMATED")
    manual_count  = sum(1 for v in indicators.values() if v["fetch_status"] == "MANUAL_REQUIRED")

    print(f"  {'#':<3} {'Indicator':<32} {'Value':<14} {'Signal':<20} {'Status':<20} {'Source Date'}")
    print(f"  {'─'*3} {'─'*32} {'─'*14} {'─'*20} {'─'*20} {'─'*20}")

    for i, key in enumerate(ORDER, 1):
        if key in GROUP_HEADERS:
            print()
            print(Fore.CYAN + f"  {GROUP_HEADERS[key]}" + Style.RESET_ALL)

        ind = indicators.get(key, {})
        val = str(ind.get("value", "?")) if ind.get("value") is not None else Fore.RED + "⚠ MISSING" + Style.RESET_ALL
        signal  = classify_signal(key, str(ind.get("value", "")))
        status  = ind.get("fetch_status", "UNKNOWN")
        date_s  = str(ind.get("data_date", ""))[:20]
        label   = LABELS.get(key, key)[:31]

        sig_str    = _sig_colour(signal)
        status_str = _status_colour(status)

        # Pad raw strings for alignment (colour codes add length)
        print(f"  {i:<3} {label:<32} {val:<14} {sig_str:<40} {status_str:<42} {date_s}")

    print()
    print(f"  {'─'*W}")
    print(f"  Source Quality:  "
          f"{Fore.GREEN}✅ Live: {live_count}{Style.RESET_ALL}  |  "
          f"{Fore.YELLOW}⚠ Estimated: {est_count}{Style.RESET_ALL}  |  "
          f"{Fore.RED}❌ Manual required: {manual_count}{Style.RESET_ALL}")
    print()

    # Print data sources section
    print(Fore.CYAN + Style.BRIGHT + "  DATA SOURCES & VERIFICATION" + Style.RESET_ALL)
    print(f"  {'─'*W}")
    for key in ORDER:
        ind = indicators.get(key, {})
        if ind:
            label   = LABELS.get(key, key)
            source  = ind.get("source", "Unknown")
            notes   = ind.get("notes", "")
            url     = ind.get("source_url", "")
            print(f"  {label:<33}: {source}")
            if url:
                print(f"  {'':>33}  URL: {Fore.BLUE}{url[:60]}{Style.RESET_ALL}")
            if notes:
                print(f"  {'':>33}  Note: {notes[:70]}")
    print(f"  {'─'*W}")
    print()

    if manual_count > 0:
        print(Fore.RED + Style.BRIGHT + f"  ⚠  {manual_count} indicator(s) have MISSING values and need manual entry!" + Style.RESET_ALL)
        print()


def prompt_action(indicators: dict) -> dict:
    """
    Interactive prompt: Accept / Override / Enter missing / Cancel.
    Returns the (possibly modified) indicators dict.
    """
    from colorama import Fore, Style
    while True:
        print(Fore.CYAN + Style.BRIGHT + "  WHAT WOULD YOU LIKE TO DO?" + Style.RESET_ALL)
        print("  [1] Accept all values and proceed to Excel update")
        print("  [2] Override a specific value (enter its number)")
        print("  [3] Enter / correct a missing value")
        print("  [4] Re-display the full table")
        print("  [5] Cancel and exit")
        print()
        choice = input("  Your choice [1-5]: ").strip()

        if choice == "1":
            missing = [k for k, v in indicators.items() if v.get("fetch_status") == "MANUAL_REQUIRED" and v.get("value") is None]
            if missing:
                print()
                print(Fore.RED + f"  ❌ Cannot proceed — {len(missing)} indicator(s) still missing:" + Style.RESET_ALL)
                for k in missing:
                    print(f"     • {LABELS.get(k, k)}")
                print("  Please enter missing values first (option [3]).")
                print()
                continue
            print(Fore.GREEN + "\n  ✅ Values accepted. Proceeding to Excel update...\n" + Style.RESET_ALL)
            return indicators

        elif choice == "2":
            print()
            for i, key in enumerate(ORDER, 1):
                ind = indicators.get(key, {})
                print(f"  [{i:>2}] {LABELS.get(key,key):<33}  Current: {ind.get('value','?')}")
            print()
            try:
                idx = int(input("  Enter indicator number to override: ").strip()) - 1
                key = ORDER[idx]
                old_val = indicators[key].get("value")
                new_val = input(f"  New value for [{LABELS[key]}] (was: {old_val}): ").strip()
                reason  = input(f"  Reason for override: ").strip()
                indicators[key]["value"]         = new_val
                indicators[key]["fetch_status"]  = "OK"
                indicators[key]["is_live"]       = False
                indicators[key]["is_estimated"]  = True
                indicators[key]["notes"]         = f"MANUAL OVERRIDE: {reason} (was: {old_val})"
                indicators[key]["source"]        = "Manual override by user"
                # Save override
                _save_override(key, old_val, new_val, reason)
                print(Fore.GREEN + f"  ✅ {LABELS[key]} updated to {new_val}" + Style.RESET_ALL)
                print()
                show_review_table(indicators)
            except (ValueError, IndexError):
                print(Fore.RED + "  ❌ Invalid number. Try again." + Style.RESET_ALL)

        elif choice == "3":
            missing = [k for k in ORDER if indicators.get(k, {}).get("fetch_status") == "MANUAL_REQUIRED"]
            if not missing:
                print(Fore.GREEN + "\n  ✅ No missing values — all indicators have data.\n" + Style.RESET_ALL)
                continue
            print()
            for i, key in enumerate(missing, 1):
                print(f"  [{i}] {LABELS.get(key, key)}")
            print()
            try:
                idx = int(input("  Which one to enter? ").strip()) - 1
                key = missing[idx]
                val = input(f"  Enter value for [{LABELS[key]}]: ").strip()
                if val:
                    indicators[key]["value"]        = val
                    indicators[key]["fetch_status"] = "OK"
                    indicators[key]["is_live"]      = False
                    indicators[key]["is_estimated"] = True
                    indicators[key]["source"]       = "Manual entry by user"
                    print(Fore.GREEN + f"  ✅ {LABELS[key]} set to {val}" + Style.RESET_ALL)
                    print()
            except (ValueError, IndexError):
                print(Fore.RED + "  ❌ Invalid choice. Try again." + Style.RESET_ALL)

        elif choice == "4":
            show_review_table(indicators)

        elif choice == "5":
            print(Fore.YELLOW + "\n  Run cancelled by user.\n" + Style.RESET_ALL)
            raise SystemExit(0)

        else:
            print(Fore.RED + "  ❌ Invalid choice. Enter 1-5." + Style.RESET_ALL)


def _save_override(key: str, old_val, new_val: str, reason: str) -> None:
    import json, datetime
    from pathlib import Path
    try:
        # Determine path relative to this file
        override_path = Path(__file__).parent.parent / "data" / "manual_overrides.json"
        override_path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        if override_path.exists():
            with open(override_path) as f:
                data = json.load(f)
        data.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "key": key, "old_value": str(old_val),
            "new_value": new_val, "reason": reason
        })
        with open(override_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Could not save override: {e}")
