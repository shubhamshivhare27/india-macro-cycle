# ============================================================
#  src/gsheet_reader.py
#  Reads manually-entered indicator values from a shared
#  Google Sheet (CSV export URL). Covers paywalled indicators.
# ============================================================

import csv
import io
import logging
import requests

logger = logging.getLogger("macro_cycle")

# Indicators that require manual entry in the Google Sheet
GSHEET_INDICATORS = {
    "pmi_manufacturing":  {"label": "PMI Manufacturing",          "type": "float",  "example": "56.4"},
    "housing_starts":     {"label": "Housing Starts / New Launches","type": "text",  "example": "Rising"},
    "earnings_growth":    {"label": "Corporate Earnings Growth %", "type": "float",  "example": "18.5"},
    "unemployment_rate":  {"label": "Unemployment Rate %",         "type": "float",  "example": "7.8"},
}


def read_gsheet_values(csv_url: str) -> dict:
    """
    Download the Google Sheet as CSV and extract indicator values.
    The sheet must have exactly two columns: Indicator_Key | Value
    Example rows:
        pmi_manufacturing   | 56.4
        housing_starts      | Rising
        earnings_growth     | 18.5
        unemployment_rate   | 7.8
    Returns dict of {key: value_string} for found indicators.
    """
    if not csv_url or csv_url.startswith("https://docs.google.com/spreadsheets/d/YOUR"):
        logger.warning("Google Sheet URL not configured. Skipping GSheet read.")
        return {}

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(csv_url, headers=headers, timeout=15)
        r.raise_for_status()
        reader = csv.reader(io.StringIO(r.text))
        values = {}
        for row in reader:
            if len(row) >= 2:
                key   = row[0].strip().lower().replace(" ", "_")
                value = row[1].strip()
                if key in GSHEET_INDICATORS and value:
                    values[key] = value
                    logger.info(f"  GSheet → {key}: {value}")
        logger.info(f"  Google Sheet: {len(values)}/{len(GSHEET_INDICATORS)} values found")
        return values
    except Exception as e:
        logger.error(f"  Google Sheet read failed: {e}")
        return {}


def prompt_missing_values(gsheet_values: dict) -> dict:
    """
    For any GSHEET indicator not found in the sheet,
    prompt the user to enter it in the terminal.
    """
    from colorama import Fore, Style
    result = dict(gsheet_values)
    for key, meta in GSHEET_INDICATORS.items():
        if key not in result or result[key] == "":
            print(f"\n  {Fore.YELLOW}⚠  {meta['label']} — not found in Google Sheet.{Style.RESET_ALL}")
            print(f"     (Type: {meta['type']} | Example: {meta['example']})")
            while True:
                val = input(f"     Enter value for [{key}]: ").strip()
                if val:
                    if meta["type"] == "float":
                        try:
                            float(val)
                            result[key] = val
                            break
                        except ValueError:
                            print("     ❌ Must be a number. Try again.")
                    elif meta["type"] == "text":
                        if key == "housing_starts" and val.title() not in ["Rising","Stable","Falling"]:
                            print("     ❌ Must be: Rising / Stable / Falling")
                        else:
                            result[key] = val.title()
                            break
                    else:
                        result[key] = val
                        break
    return result


def get_gsheet_and_prompt(csv_url: str) -> dict:
    """Full pipeline: read GSheet, then prompt for anything missing."""
    values = read_gsheet_values(csv_url)
    values = prompt_missing_values(values)
    return values
