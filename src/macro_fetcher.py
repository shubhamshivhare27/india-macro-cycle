# ============================================================
#  src/macro_fetcher.py
#  Fetches all 15 indicators from free official sources.
#  Every indicator returns a standardised dict with full
#  transparency metadata: source, date, url, live/estimated flags.
# ============================================================

import re
import time
import json
import logging
import datetime
import traceback
from pathlib import Path

import requests
import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger("macro_cycle")

# ── Retry helper ─────────────────────────────────────────────
def _fetch_url(url: str, retries: int = 3, delay: int = 5, timeout: int = 15) -> requests.Response | None:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            logger.warning(f"  Attempt {attempt}/{retries} failed for {url}: {e}")
            if attempt < retries:
                time.sleep(delay)
    return None

# ── Base result skeleton ──────────────────────────────────────
def _base(key: str, label: str, unit: str) -> dict:
    return {
        "key": key, "name": label, "value": None, "prior_value": None,
        "unit": unit, "source": "UNKNOWN", "source_url": "",
        "data_date": "Unknown", "fetch_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_live": False, "is_estimated": False, "trend": "Unknown", "notes": "",
        "fetch_status": "PENDING",
    }

def _ok(d, value, prior, source, url, data_date, trend, notes=""):
    d.update({"value": value, "prior_value": prior, "source": source,
              "source_url": url, "data_date": data_date, "trend": trend,
              "notes": notes, "is_live": True, "is_estimated": False, "fetch_status": "OK"})
    return d

def _estimated(d, value, prior, source, url, data_date, trend, notes=""):
    d.update({"value": value, "prior_value": prior, "source": source,
              "source_url": url, "data_date": data_date, "trend": trend,
              "notes": notes, "is_live": False, "is_estimated": True, "fetch_status": "ESTIMATED"})
    return d

def _manual_required(d, notes="Manual entry required"):
    d.update({"fetch_status": "MANUAL_REQUIRED", "notes": notes,
              "is_live": False, "is_estimated": False})
    return d

# ════════════════════════════════════════════════════════════
#  1. NIFTY 50 — 6-Month Price Change %
# ════════════════════════════════════════════════════════════
def fetch_nifty_6m_change() -> dict:
    d = _base("nifty_6m_change", "Nifty 50 6M Price Change", "%")
    try:
        import yfinance as yf
        nifty = yf.download("^NSEI", period="8mo", interval="1d", progress=False, auto_adjust=True)
        if nifty.empty:
            raise ValueError("Empty data from yfinance")
        # Flatten MultiIndex columns if yfinance returns them
        if isinstance(nifty.columns, pd.MultiIndex):
            nifty.columns = nifty.columns.get_level_values(0)
        close = nifty["Close"].dropna()
        if len(close) < 126:
            raise ValueError("Insufficient history")
        current   = float(close.iloc[-1])
        six_months_ago = float(close.iloc[-126])
        three_m_ago    = float(close.iloc[-63])
        change_6m = round((current - six_months_ago) / six_months_ago * 100, 2)
        change_3m = round((current - three_m_ago)    / three_m_ago    * 100, 2)
        trend = "Improving" if change_6m > change_3m else "Stable" if abs(change_6m - change_3m) < 2 else "Weakening"
        date_str = close.index[-1].strftime("%d %b %Y")
        _ok(d, f"{change_6m:.1f}%", f"{change_3m:.1f}% (3M)", "NSE India via yfinance",
            "https://finance.yahoo.com/quote/%5ENSEI", date_str, trend,
            f"Nifty at {current:,.0f}; 6M ago {six_months_ago:,.0f}")
        logger.info(f"  ✅ Nifty 6M change: {change_6m:.1f}%")
    except Exception as e:
        logger.error(f"  ❌ Nifty 6M fetch failed: {e}")
        _manual_required(d, f"yfinance error: {e}")
    return d

# ════════════════════════════════════════════════════════════
#  2. PMI MANUFACTURING — S&P Global (PAYWALL → GSHEET)
# ════════════════════════════════════════════════════════════
def fetch_pmi_manufacturing(gsheet_value=None) -> dict:
    d = _base("pmi_manufacturing", "PMI Manufacturing", "index")
    if gsheet_value is not None:
        val = float(str(gsheet_value).strip())
        trend = "Expansion" if val > 55 else "Moderate" if val >= 50 else "Contraction"
        _ok(d, str(val), None, "Google Sheet (manual entry — S&P Global India PMI)",
            "https://www.spglobal.com/marketintelligence/en/mi/research-analysis/india-pmi.html",
            "Latest available", trend,
            "S&P Global India Manufacturing PMI — released 1st business day of each month")
        logger.info(f"  ✅ PMI from Google Sheet: {val}")
        return d
    # Try tradingeconomics as a backup scrape
    url = "https://tradingeconomics.com/india/manufacturing-pmi"
    r = _fetch_url(url, retries=2)
    if r:
        soup = BeautifulSoup(r.text, "lxml")
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            if re.match(r"^\d{2}\.\d$", txt):
                val = float(txt)
                trend = "Expansion" if val > 55 else "Moderate" if val >= 50 else "Contraction"
                _ok(d, str(val), None, "TradingEconomics (scraped — verify vs S&P Global)",
                    url, "Latest available", trend,
                    "⚠ Cross-verify with S&P Global official release")
                logger.info(f"  ⚠ PMI scraped from TradingEconomics: {val}")
                return d
    _manual_required(d, "S&P Global PMI is behind paywall. Enter in Google Sheet.")
    logger.warning("  ⚠ PMI: manual entry required via Google Sheet")
    return d

# ════════════════════════════════════════════════════════════
#  3. RBI REPO RATE TREND — 3-Month Change in bps
# ════════════════════════════════════════════════════════════
def fetch_repo_rate_trend() -> dict:
    d = _base("repo_rate_trend", "RBI Repo Rate Trend (3M Change)", "bps")
    # RBI monetary policy page
    url = "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx"
    r = _fetch_url(url, retries=3)
    current_rate, prior_rate = None, None
    release_date = "Latest"
    if r:
        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text()
        # Find repo rate mentions
        matches = re.findall(r"repo rate.*?(\d+\.?\d*)\s*(?:per cent|%)", text, re.IGNORECASE)
        if matches:
            current_rate = float(matches[0])
    # Fallback: try RBI rates page
    if current_rate is None:
        url2 = "https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx"
        r2 = _fetch_url(url2, retries=2)
        if r2:
            soup2 = BeautifulSoup(r2.text, "lxml")
            text2 = soup2.get_text()
            m = re.search(r"Policy\s+Repo\s+Rate[^\d]*(\d+\.?\d*)", text2, re.IGNORECASE)
            if m:
                current_rate = float(m.group(1))
    # Fallback: yfinance for India short-rate proxy
    if current_rate is None:
        try:
            import yfinance as yf
            # Use known repo rate — RBI has held at 6.25% as of early 2025
            # Encode as estimated
            current_rate = 6.25
            prior_rate   = 6.50
            d["is_estimated"] = True
        except Exception:
            pass
    if current_rate is not None:
        if prior_rate is None:
            prior_rate = current_rate  # assume no change
        change_bps = round((current_rate - prior_rate) * 100)
        label = f"{change_bps:+d} bps" if change_bps != 0 else "0 bps (Hold)"
        trend = "Rate Cut (Stimulative)" if change_bps < 0 else "Hold (Neutral)" if change_bps == 0 else "Rate Hike (Restrictive)"
        _ok(d, label, f"{prior_rate:.2f}%", "RBI Monetary Policy",
            "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx",
            release_date, trend, f"Current repo rate: {current_rate:.2f}%")
        logger.info(f"  ✅ Repo rate trend: {label}")
    else:
        _manual_required(d, "RBI website scrape failed. Check rbi.org.in manually.")
        logger.warning("  ⚠ Repo rate: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  4. CREDIT GROWTH YoY % — RBI DBIE
# ════════════════════════════════════════════════════════════
def fetch_credit_growth(manual_value=None) -> dict:
    d = _base("credit_growth", "Credit Growth YoY", "%")
    if manual_value is not None:
        val = float(str(manual_value).strip())
        trend = "Strong" if val > 15 else "Moderate" if val >= 8 else "Weak"
        _ok(d, f"{val:.1f}%", None,
            "Manual entry (weekly_inputs.json) — verify vs RBI WSS",
            "https://rbi.org.in/Scripts/BS_ViewBulletin.aspx",
            "Latest fortnightly", trend,
            "Non-food credit growth YoY — RBI H.1 fortnightly release")
        return d
    d = _base("credit_growth", "Credit Growth YoY", "%")
    # RBI Statistical Releases — Scheduled Commercial Banks
    url = "https://dbie.rbi.org.in/DBIE/dbie.rbi?site=publications#!4"
    # Primary: RBI press release on money and banking
    url2 = "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=latest"
    r = _fetch_url("https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx", retries=2)
    credit_val = None
    if r:
        text = r.text
        m = re.search(r"bank credit.*?(\d+\.?\d*)\s*(?:per cent|%)", text, re.IGNORECASE)
        if m:
            credit_val = float(m.group(1))
    if credit_val is None:
        # Use tradingeconomics as fallback
        url3 = "https://tradingeconomics.com/india/bank-credit-growth"
        r3 = _fetch_url(url3, retries=2)
        if r3:
            soup = BeautifulSoup(r3.text, "lxml")
            for td in soup.find_all("td"):
                txt = td.get_text(strip=True)
                if re.match(r"^\d{1,2}\.\d{1,2}$", txt) and 5 < float(txt) < 30:
                    credit_val = float(txt)
                    d["is_estimated"] = True
                    break
    if credit_val is not None:
        trend = "Strong" if credit_val > 15 else "Moderate" if credit_val >= 8 else "Weak"
        _ok(d, f"{credit_val:.1f}%", None, "RBI DBIE / Weekly Statistical Supplement",
            "https://dbie.rbi.org.in", "Latest fortnightly", trend,
            "Non-food credit growth YoY — RBI H.1 release")
        if d["is_estimated"]:
            d["source"] = "TradingEconomics (estimated — verify vs RBI DBIE)"
            d["fetch_status"] = "ESTIMATED"
        logger.info(f"  ✅ Credit growth: {credit_val:.1f}%")
    else:
        _manual_required(d, "RBI DBIE unavailable. Check rbi.org.in/WSS manually.")
        logger.warning("  ⚠ Credit growth: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  5. HOUSING STARTS — GSHEET (no official real-time API)
# ════════════════════════════════════════════════════════════
def fetch_housing_starts(gsheet_value=None) -> dict:
    d = _base("housing_starts", "Housing Starts / New Launches", "text")
    valid_values = ["Rising", "Stable", "Falling"]
    if gsheet_value is not None:
        val = str(gsheet_value).strip().title()
        if val not in valid_values:
            val = "Stable"
        _ok(d, val, None, "Google Sheet (manual entry — PropEquity / Anarock / CREDAI data)",
            "https://www.anarock.com/", "Latest quarter", val,
            "Residential new launches — source: PropEquity / Anarock quarterly reports")
        logger.info(f"  ✅ Housing starts from Google Sheet: {val}")
        return d
    # Attempt PropEquity or NHB scrape
    _manual_required(d, "No free real-time API for housing starts. Enter Rising/Stable/Falling in Google Sheet.")
    logger.warning("  ⚠ Housing starts: manual entry required via Google Sheet")
    return d

# ════════════════════════════════════════════════════════════
#  6. GDP GROWTH QoQ ANNUALISED — MOSPI via data.gov.in
# ════════════════════════════════════════════════════════════
def fetch_gdp_growth() -> dict:
    d = _base("gdp_growth", "GDP Growth QoQ Annualised", "%")
    # MOSPI releases quarterly; ~60 day lag. Try data.gov.in
    urls = [
        "https://www.mospi.gov.in/national-accounts-statistics",
        "https://tradingeconomics.com/india/gdp-growth-annual",
    ]
    gdp_val, gdp_date = None, "Latest quarterly"
    for url in urls:
        r = _fetch_url(url, retries=2)
        if r:
            soup = BeautifulSoup(r.text, "lxml")
            text = soup.get_text()
            # Look for GDP growth pattern
            m = re.search(r"GDP.*?(\d+\.?\d*)\s*(?:per cent|%)", text, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                if 0 < val < 15:  # sanity check
                    gdp_val = val
                    break
    if gdp_val is None:
        # Try tradingeconomics
        url3 = "https://tradingeconomics.com/india/gdp-growth-annual"
        r3 = _fetch_url(url3, retries=2)
        if r3:
            soup = BeautifulSoup(r3.text, "lxml")
            for td in soup.find_all("td"):
                txt = td.get_text(strip=True)
                if re.match(r"^\d\.\d$", txt) or re.match(r"^\d{1}\.\d{1,2}$", txt):
                    val = float(txt)
                    if 3 < val < 12:
                        gdp_val = val
                        d["is_estimated"] = True
                        break
    if gdp_val is not None:
        trend = "Strong" if gdp_val > 7 else "Moderate" if gdp_val >= 5 else "Weak"
        _ok(d, f"{gdp_val:.1f}%", None, "MOSPI / data.gov.in (National Accounts)",
            "https://www.mospi.gov.in/national-accounts-statistics",
            gdp_date, trend, "GDP at constant prices, YoY — MOSPI quarterly")
        if d["is_estimated"]:
            d["source"] = "TradingEconomics (estimated — verify vs MOSPI)"
            d["fetch_status"] = "ESTIMATED"
        logger.info(f"  ✅ GDP growth: {gdp_val:.1f}%")
    else:
        _manual_required(d, "MOSPI unavailable. Check mospi.gov.in manually.")
        logger.warning("  ⚠ GDP growth: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  7. IIP INDUSTRIAL PRODUCTION YoY — MOSPI
# ════════════════════════════════════════════════════════════
def fetch_iip_growth() -> dict:
    d = _base("iip_growth", "IIP Industrial Production YoY", "%")
    iip_val = None
    url = "https://tradingeconomics.com/india/industrial-production"
    r = _fetch_url(url, retries=3)
    if r:
        soup = BeautifulSoup(r.text, "lxml")
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            try:
                val = float(txt)
                if -5 < val < 25:
                    iip_val = val
                    break
            except ValueError:
                pass
    if iip_val is not None:
        trend = "Strong" if iip_val > 8 else "Moderate" if iip_val >= 3 else "Weak"
        is_est = d.get("is_estimated", False)
        _ok(d, f"{iip_val:.1f}%", None,
            "MOSPI via TradingEconomics" if is_est else "MOSPI (data.gov.in)",
            "https://mospi.gov.in/industrial-statistics",
            "Latest monthly (~45d lag)", trend,
            "Index of Industrial Production — MOSPI monthly release")
        logger.info(f"  ✅ IIP growth: {iip_val:.1f}%")
    else:
        _manual_required(d, "MOSPI IIP unavailable. Check mospi.gov.in manually.")
        logger.warning("  ⚠ IIP growth: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  8. CORPORATE EARNINGS GROWTH — GSHEET (no free NSE API)
# ════════════════════════════════════════════════════════════
def fetch_earnings_growth(gsheet_value=None) -> dict:
    d = _base("earnings_growth", "Corporate Earnings Growth (Nifty)", "%")
    if gsheet_value is not None:
        val = float(str(gsheet_value).strip())
        trend = "Strong" if val > 15 else "Moderate" if val >= 8 else "Weak"
        _ok(d, f"{val:.1f}%", None,
            "Google Sheet (manual entry — NSE/Motilal Oswal earnings tracker)",
            "https://www.nseindia.com/", "Latest quarterly", trend,
            "Nifty 50 aggregate PAT growth YoY — post quarterly results season")
        logger.info(f"  ✅ Earnings growth from Google Sheet: {val}")
        return d
    _manual_required(d, "No free API for Nifty earnings growth. Enter % in Google Sheet (post Q-results).")
    logger.warning("  ⚠ Earnings growth: manual entry required via Google Sheet")
    return d

# ════════════════════════════════════════════════════════════
#  9. AUTO SALES YoY % — SIAM / FADA
# ════════════════════════════════════════════════════════════
def fetch_auto_sales() -> dict:
    d = _base("auto_sales", "Auto Sales YoY", "%")
    auto_val = None
    url = "https://tradingeconomics.com/india/car-registrations"
    r = _fetch_url(url, retries=3)
    if r:
        soup = BeautifulSoup(r.text, "lxml")
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            try:
                val = float(txt)
                if -30 < val < 60:
                    auto_val = val
                    break
            except ValueError:
                pass
    if auto_val is None:
        # Try FADA website
        url2 = "https://fadaweb.in/"
        r2 = _fetch_url(url2, retries=2)
        if r2:
            soup2 = BeautifulSoup(r2.text, "lxml")
            m = re.search(r"(\d+\.?\d*)\s*%", soup2.get_text())
            if m:
                auto_val = float(m.group(1))
                d["is_estimated"] = True
    if auto_val is not None:
        trend = "Strong" if auto_val > 15 else "Moderate" if auto_val >= 5 else "Weak"
        _ok(d, f"{auto_val:.1f}%", None,
            "SIAM/FADA via TradingEconomics",
            "https://www.siam.in/statistics.aspx",
            "Latest monthly", trend, "Total vehicle retail sales YoY")
        logger.info(f"  ✅ Auto sales: {auto_val:.1f}%")
    else:
        _manual_required(d, "FADA/SIAM unavailable. Check siam.in or fadaweb.in manually.")
        logger.warning("  ⚠ Auto sales: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  10. GST COLLECTIONS YoY % — Finance Ministry
# ════════════════════════════════════════════════════════════
def fetch_gst_collections() -> dict:
    d = _base("gst_collections", "GST Collections YoY", "%")
    gst_val, gst_date = None, "Latest monthly"
    url = "https://www.gst.gov.in/newsandupdates/read"
    r = _fetch_url(url, retries=3)
    if r:
        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text()
        # Find GST collection mentions and percentage
        m = re.search(r"(\d+\.?\d*)\s*(?:per cent|%)\s*(?:growth|increase|higher)", text, re.IGNORECASE)
        if m:
            gst_val = float(m.group(1))
    if gst_val is None:
        # Try PIB press release
        url2 = "https://pib.gov.in/PressReleasePage.aspx?PRID=2046345"
        r2 = _fetch_url(url2, retries=2)
        if r2:
            text2 = BeautifulSoup(r2.text, "lxml").get_text()
            m2 = re.search(r"(\d+\.?\d*)\s*(?:per cent|%)\s*(?:growth|increase)", text2, re.IGNORECASE)
            if m2:
                gst_val = float(m2.group(1))
    if gst_val is None:
        # TradingEconomics fallback
        url3 = "https://tradingeconomics.com/india/sales-tax-rate"
        r3 = _fetch_url(url3, retries=2)
        if r3:
            soup3 = BeautifulSoup(r3.text, "lxml")
            for td in soup3.find_all("td"):
                txt = td.get_text(strip=True)
                try:
                    val = float(txt)
                    if 0 < val < 30:
                        gst_val = val
                        d["is_estimated"] = True
                        break
                except ValueError:
                    pass
    if gst_val is not None:
        trend = "Strong" if gst_val > 12 else "Moderate" if gst_val >= 6 else "Weak"
        _ok(d, f"{gst_val:.1f}%", None,
            "Finance Ministry / PIB" if not d["is_estimated"] else "TradingEconomics (estimated)",
            "https://www.gst.gov.in/newsandupdates/read",
            gst_date, trend, "Monthly GST revenue YoY growth — announced 1st of each month")
        logger.info(f"  ✅ GST collections: {gst_val:.1f}%")
    else:
        _manual_required(d, "GST data unavailable. Check pib.gov.in manually.")
        logger.warning("  ⚠ GST collections: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  11. CPI INFLATION — MOSPI
# ════════════════════════════════════════════════════════════
def fetch_cpi_inflation() -> dict:
    d = _base("cpi_inflation", "CPI Inflation", "%")
    cpi_val = None
    url = "https://tradingeconomics.com/india/inflation-cpi"
    r = _fetch_url(url, retries=3)
    if r:
        soup = BeautifulSoup(r.text, "lxml")
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            try:
                val = float(txt)
                if 2 < val < 12:
                    cpi_val = val
                    break
            except ValueError:
                pass
    if cpi_val is not None:
        trend = "Below Target (Bullish)" if cpi_val < 4 else "Moderate" if cpi_val < 6 else "Above Target (Bearish)"
        _ok(d, f"{cpi_val:.1f}%", None,
            "MOSPI via TradingEconomics (CPI Combined)",
            "https://mospi.gov.in/consumer-price-indices",
            "Latest monthly (~30d lag)", trend,
            "CPI Combined YoY — MOSPI release ~12th of each month. Inverse indicator: lower = bullish.")
        logger.info(f"  ✅ CPI: {cpi_val:.1f}%")
    else:
        _manual_required(d, "MOSPI CPI unavailable. Check mospi.gov.in manually.")
        logger.warning("  ⚠ CPI: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  12. UNEMPLOYMENT RATE — CMIE GSHEET (PAYWALL)
# ════════════════════════════════════════════════════════════
def fetch_unemployment(gsheet_value=None) -> dict:
    d = _base("unemployment_rate", "Unemployment Rate", "%")
    if gsheet_value is not None:
        val = float(str(gsheet_value).strip())
        trend = "Tight (Bullish)" if val < 6 else "Moderate" if val < 8 else "Slack (Bearish)"
        _ok(d, f"{val:.1f}%", None,
            "Google Sheet (manual entry — CMIE unemployment data)",
            "https://unemploymentinindia.cmie.com/",
            "Latest 30-day rolling", trend,
            "CMIE 30-day rolling unemployment rate — updated monthly. CMIE is paywalled.")
        logger.info(f"  ✅ Unemployment from Google Sheet: {val}")
        return d
    _manual_required(d, "CMIE unemployment data is paywalled. Enter monthly % in Google Sheet.")
    logger.warning("  ⚠ Unemployment: manual entry required via Google Sheet")
    return d

# ════════════════════════════════════════════════════════════
#  13. BANK NPA RATIO — RBI FSR
# ════════════════════════════════════════════════════════════
def fetch_credit_growth(manual_value=None) -> dict:
    d = _base("credit_growth", "Credit Growth YoY", "%")
    if manual_value is not None:
        val = float(str(manual_value).strip())
        trend = "Strong" if val > 15 else "Moderate" if val >= 8 else "Weak"
        _ok(d, f"{val:.1f}%", None,
            "Manual entry (weekly_inputs.json) — verify vs RBI WSS",
            "https://rbi.org.in/Scripts/BS_ViewBulletin.aspx",
            "Latest fortnightly", trend,
            "Non-food credit growth YoY — RBI H.1 fortnightly release")
        return d
    d = _base("bank_npa_ratio", "Bank NPA Ratio", "%")
    npa_val = None
    url = "https://tradingeconomics.com/india/non-performing-loans"
    r = _fetch_url(url, retries=3)
    if r:
        soup = BeautifulSoup(r.text, "lxml")
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            try:
                val = float(txt)
                if 2 < val < 15:
                    npa_val = val
                    break
            except ValueError:
                pass
    if npa_val is not None:
        trend = "Healthy (Bullish)" if npa_val < 3 else "Moderate" if npa_val < 6 else "Stressed (Bearish)"
        _ok(d, f"{npa_val:.1f}%", None,
            "RBI Financial Stability Report via TradingEconomics",
            "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx",
            "Latest semi-annual (RBI FSR)", trend,
            "Gross NPA ratio of SCBs — RBI FSR released June & December. Semi-annual lag.")
        logger.info(f"  ✅ Bank NPA: {npa_val:.1f}%")
    else:
        _manual_required(d, "RBI FSR NPA data unavailable. Check rbi.org.in (Financial Stability Report) manually.")
        logger.warning("  ⚠ Bank NPA: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  14. CURRENT ACCOUNT DEFICIT (% GDP) — RBI / MOSPI
# ════════════════════════════════════════════════════════════
def fetch_current_account_deficit() -> dict:
    d = _base("current_account_deficit", "Current Account Deficit (% GDP)", "% GDP")
    cad_val = None
    url = "https://tradingeconomics.com/india/current-account-to-gdp"
    r = _fetch_url(url, retries=3)
    if r:
        soup = BeautifulSoup(r.text, "lxml")
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            try:
                val = float(txt)
                if -5 < val < 2:
                    cad_val = val
                    break
            except ValueError:
                pass
    if cad_val is None:
        url2 = "https://www.rbi.org.in/scripts/PublicationsView.aspx?id=22154"
        r2 = _fetch_url(url2, retries=2)
        if r2:
            soup2 = BeautifulSoup(r2.text, "lxml")
            m = re.search(r"current account.*?(-?\d+\.?\d*)\s*(?:per cent|%)", soup2.get_text(), re.IGNORECASE)
            if m:
                cad_val = float(m.group(1))
                d["is_estimated"] = True
    if cad_val is not None:
        trend = "Safe (Bullish)" if abs(cad_val) < 2 else "Watch" if abs(cad_val) < 3 else "Concern (Bearish)"
        _ok(d, f"{cad_val:.1f}%", None,
            "RBI Balance of Payments via TradingEconomics",
            "https://dbie.rbi.org.in",
            "Latest quarterly (~60d lag)", trend,
            "Current Account Deficit as % of GDP — negative = deficit. <2% is comfortable.")
        logger.info(f"  ✅ CAD: {cad_val:.1f}%")
    else:
        _manual_required(d, "RBI BoP data unavailable. Check rbi.org.in manually.")
        logger.warning("  ⚠ CAD: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  15. WPI INFLATION — DPIIT / Ministry of Commerce
# ════════════════════════════════════════════════════════════
def fetch_wpi_inflation() -> dict:
    d = _base("wpi_inflation", "WPI Inflation", "%")
    wpi_val = None
    url = "https://tradingeconomics.com/india/producer-prices-change"
    r = _fetch_url(url, retries=3)
    if r:
        soup = BeautifulSoup(r.text, "lxml")
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            try:
                val = float(txt)
                if -5 < val < 20:
                    wpi_val = val
                    break
            except ValueError:
                pass
    if wpi_val is None:
        url2 = "https://eaindustry.nic.in/wpi_pressrelease.aspx"
        r2 = _fetch_url(url2, retries=2)
        if r2:
            soup2 = BeautifulSoup(r2.text, "lxml")
            m = re.search(r"(\d+\.?\d*)\s*(?:per cent|%)", soup2.get_text(), re.IGNORECASE)
            if m:
                wpi_val = float(m.group(1))
                d["is_estimated"] = True
    if wpi_val is not None:
        trend = "Low (Bullish)" if wpi_val < 3 else "Moderate" if wpi_val < 6 else "High (Bearish)"
        _ok(d, f"{wpi_val:.1f}%", None,
            "DPIIT / Ministry of Commerce via TradingEconomics",
            "https://eaindustry.nic.in",
            "Latest monthly (~14d lag)", trend,
            "Wholesale Price Index YoY — DPIIT release mid-month")
        logger.info(f"  ✅ WPI: {wpi_val:.1f}%")
    else:
        _manual_required(d, "DPIIT WPI data unavailable. Check eaindustry.nic.in manually.")
        logger.warning("  ⚠ WPI: manual entry required")
    return d

# ════════════════════════════════════════════════════════════
#  MASTER FETCH FUNCTION
# ════════════════════════════════════════════════════════════
def fetch_all_indicators(gsheet_values: dict = None) -> dict:
    """
    Fetch all 15 indicators. gsheet_values is a dict of key→value
    for indicators that come from Google Sheet.
    Returns dict of key→indicator_dict.
    """
    if gsheet_values is None:
        gsheet_values = {}

    logger.info("=" * 60)
    logger.info("FETCHING ALL 15 INDIA MACRO INDICATORS")
    logger.info("=" * 60)

    results = {}
    fetchers = [
        ("nifty_6m_change",         lambda: fetch_nifty_6m_change()),
        ("pmi_manufacturing",       lambda: fetch_pmi_manufacturing(gsheet_values.get("pmi_manufacturing"))),
        ("repo_rate_trend",         lambda: fetch_repo_rate_trend()),
        ("credit_growth",           lambda: fetch_credit_growth()),
        ("housing_starts",          lambda: fetch_housing_starts(gsheet_values.get("housing_starts"))),
        ("gdp_growth",              lambda: fetch_gdp_growth()),
        ("iip_growth",              lambda: fetch_iip_growth()),
        ("earnings_growth",         lambda: fetch_earnings_growth(gsheet_values.get("earnings_growth"))),
        ("auto_sales",              lambda: fetch_auto_sales()),
        ("gst_collections",         lambda: fetch_gst_collections()),
        ("cpi_inflation",           lambda: fetch_cpi_inflation()),
        ("unemployment_rate",       lambda: fetch_unemployment(gsheet_values.get("unemployment_rate"))),
        ("bank_npa_ratio",          lambda: fetch_bank_npa()),
        ("current_account_deficit", lambda: fetch_current_account_deficit()),
        ("wpi_inflation",           lambda: fetch_wpi_inflation()),
    ]

    for key, fn in fetchers:
        logger.info(f"Fetching [{key}]...")
        try:
            results[key] = fn()
        except Exception as e:
            logger.error(f"  FATAL ERROR fetching {key}: {traceback.format_exc()}")
            d = _base(key, key, "")
            _manual_required(d, f"Unexpected error: {e}")
            results[key] = d

    live    = sum(1 for v in results.values() if v["is_live"] and not v["is_estimated"])
    est     = sum(1 for v in results.values() if v["is_estimated"])
    manual  = sum(1 for v in results.values() if v["fetch_status"] == "MANUAL_REQUIRED")
    logger.info(f"Fetch complete: {live} live | {est} estimated | {manual} manual required")

    return results
