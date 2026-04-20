# ============================================================
#  src/report_sender.py
#  Builds an HTML email with all 7 sections and sends
#  via Gmail SMTP.
#
#  NEW — Section G: Source Verification Table
#  For every indicator shows:
#    • Exact value used in calculation
#    • Signal (Bullish/Neutral/Bearish) with threshold shown
#    • Primary official source with direct clickable URL
#    • Second source URL to cross-check in one click
#    • Release schedule & max data staleness
#    • How the system fetched the value
#    • Why this indicator matters for the cycle
# ============================================================

import smtplib
import logging
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text       import MIMEText
from pathlib import Path

logger = logging.getLogger("macro_cycle")

PHASE_COLOURS_HEX = {
    "STRONG RECOVERY": "#1a7f37",
    "EARLY EXPANSION": "#2d8b56",
    "MID CYCLE":       "#b7950b",
    "LATE CYCLE":      "#8e44ad",
    "CONTRACTION":     "#c0392b",
}
STATUS_COLOURS = {
    "OK":               "#d4edda",
    "ESTIMATED":        "#fff3cd",
    "MANUAL_REQUIRED":  "#f8d7da",
}

# ── Master verification registry ─────────────────────────────
VERIFICATION_REGISTRY = {
    "nifty_6m_change": {
        "label":           "Nifty 50 6M Price Change",
        "official_source": "NSE India",
        "official_url":    "https://www.nseindia.com/market-data/live-equity-market",
        "verify_url":      "https://finance.yahoo.com/quote/%5ENSEI",
        "verify_label":    "Yahoo Finance ^NSEI",
        "release_schedule":"Daily (live price)",
        "max_staleness":   "1 trading day",
        "fetch_method":    "Auto — yfinance live NSE price",
        "threshold_note":  ">10% = Bullish | 0–10% = Neutral | <0% = Bearish",
        "why_it_matters":  "Equity market leads the economy by 3–6 months — rising 6M return signals broad economic optimism ahead",
    },
    "pmi_manufacturing": {
        "label":           "PMI Manufacturing",
        "official_source": "S&P Global India Manufacturing PMI",
        "official_url":    "https://www.spglobal.com/marketintelligence/en/mi/research-analysis/india-pmi.html",
        "verify_url":      "https://economictimes.indiatimes.com/topic/india-pmi",
        "verify_label":    "Economic Times — India PMI",
        "release_schedule":"Monthly (1st business day of month)",
        "max_staleness":   "~4 weeks",
        "fetch_method":    "Manual — weekly_inputs.json (S&P Global paywalled; headline free in ET/BS)",
        "threshold_note":  ">55 = Bullish | 50–55 = Neutral | <50 = Bearish",
        "why_it_matters":  "Highest-frequency demand signal — purchasing managers see order trends before any official data is collected",
    },
    "repo_rate_trend": {
        "label":           "RBI Repo Rate Trend (3M Change)",
        "official_source": "Reserve Bank of India — MPC Press Release",
        "official_url":    "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx",
        "verify_url":      "https://tradingeconomics.com/india/interest-rate",
        "verify_label":    "TradingEconomics — India Interest Rate",
        "release_schedule":"Bi-monthly (every ~6 weeks)",
        "max_staleness":   "~6 weeks",
        "fetch_method":    "Auto — RBI website scrape",
        "threshold_note":  "Rate cut = Bullish | Hold = Neutral | Rate hike = Bearish",
        "why_it_matters":  "Rate direction drives credit cost, banking NIMs, real-estate demand and capital flows — the most direct policy lever",
    },
    "credit_growth": {
        "label":           "Bank Credit Growth YoY",
        "official_source": "RBI Weekly Statistical Supplement (H.1)",
        "official_url":    "https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx",
        "verify_url":      "https://dbie.rbi.org.in/DBIE/dbie.rbi?site=publications",
        "verify_label":    "RBI DBIE Database",
        "release_schedule":"Fortnightly",
        "max_staleness":   "~2 weeks",
        "fetch_method":    "Manual — weekly_inputs.json (check rbi.org.in/WSS fortnightly)",
        "threshold_note":  ">15% = Bullish | 8–15% = Neutral | <8% = Bearish",
        "why_it_matters":  "Credit is the fuel of economic expansion — above 15% confirms expansion; below 8% is a recessionary warning signal",
    },
    "housing_starts": {
        "label":           "Housing Starts / New Launches",
        "official_source": "Anarock Research (quarterly report)",
        "official_url":    "https://www.anarock.com/research",
        "verify_url":      "https://www.propequity.in/Research",
        "verify_label":    "PropEquity Research",
        "release_schedule":"Quarterly",
        "max_staleness":   "~13 weeks",
        "fetch_method":    "Manual — weekly_inputs.json (update quarterly: Rising / Stable / Falling)",
        "threshold_note":  "Rising = Bullish | Stable = Neutral | Falling = Bearish",
        "why_it_matters":  "New launches lead cement, steel, consumer durables and NBFC demand by 12–18 months — key capex cycle signal",
    },
    "gdp_growth": {
        "label":           "GDP Growth QoQ Annualised",
        "official_source": "MOSPI — National Accounts Statistics",
        "official_url":    "https://www.mospi.gov.in/national-accounts-statistics",
        "verify_url":      "https://tradingeconomics.com/india/gdp-growth-annual",
        "verify_label":    "TradingEconomics — India GDP Growth",
        "release_schedule":"Quarterly (released ~60 days after quarter end)",
        "max_staleness":   "~4 months",
        "fetch_method":    "Auto — MOSPI / TradingEconomics scrape",
        "threshold_note":  ">7% = Bullish | 5–7% = Neutral | <5% = Bearish",
        "why_it_matters":  "The headline coincident indicator — confirms whether the economy actually grew at the rate PMI and IIP suggested",
    },
    "iip_growth": {
        "label":           "IIP Industrial Production YoY",
        "official_source": "MOSPI — Index of Industrial Production",
        "official_url":    "https://mospi.gov.in/industrial-statistics",
        "verify_url":      "https://tradingeconomics.com/india/industrial-production",
        "verify_label":    "TradingEconomics — India IIP",
        "release_schedule":"Monthly (released ~45 days after month end)",
        "max_staleness":   "~6 weeks",
        "fetch_method":    "Auto — MOSPI / TradingEconomics scrape",
        "threshold_note":  ">8% = Bullish | 3–8% = Neutral | <3% = Bearish",
        "why_it_matters":  "Measures actual factory output — leads corporate earnings by one quarter; validates or challenges the PMI reading",
    },
    "earnings_growth": {
        "label":           "Corporate Earnings Growth (Nifty PAT)",
        "official_source": "NSE India / Motilal Oswal Quarterly Tracker",
        "official_url":    "https://www.nseindia.com/reports/smf-data",
        "verify_url":      "https://www.motilaloswal.com/blog-and-articles/nifty-earnings/",
        "verify_label":    "Motilal Oswal — Nifty Earnings Tracker",
        "release_schedule":"Quarterly (Apr, Jul, Oct, Jan — after results season)",
        "max_staleness":   "~13 weeks",
        "fetch_method":    "Manual — weekly_inputs.json (update after quarterly results season)",
        "threshold_note":  ">15% = Bullish | 8–15% = Neutral | <8% = Bearish",
        "why_it_matters":  "Actual PAT growth confirms whether macro conditions are translating into real corporate profits — the ultimate test",
    },
    "auto_sales": {
        "label":           "Auto Sales YoY",
        "official_source": "FADA — Federation of Automobile Dealers",
        "official_url":    "https://www.fadaweb.in/",
        "verify_url":      "https://www.siam.in/statistics.aspx",
        "verify_label":    "SIAM — Society of Indian Automobile Manufacturers",
        "release_schedule":"Monthly (1st week of following month)",
        "max_staleness":   "~5 weeks",
        "fetch_method":    "Auto — SIAM/FADA via TradingEconomics scrape",
        "threshold_note":  ">15% = Bullish | 5–15% = Neutral | <5% = Bearish",
        "why_it_matters":  "Auto retail is the broadest real-time consumption indicator — captures urban and rural demand across all income segments",
    },
    "gst_collections": {
        "label":           "GST Collections YoY",
        "official_source": "Finance Ministry / Press Information Bureau",
        "official_url":    "https://pib.gov.in/",
        "verify_url":      "https://www.gst.gov.in/newsandupdates/read",
        "verify_label":    "GST Council — Official Updates",
        "release_schedule":"Monthly (1st of each month, previous month data)",
        "max_staleness":   "~5 weeks",
        "fetch_method":    "Auto — PIB / Finance Ministry scrape",
        "threshold_note":  ">12% = Bullish | 6–12% = Neutral | <6% = Bearish",
        "why_it_matters":  "Every transaction in the economy generates GST — YoY growth is the most real-time proxy for nominal GDP growth",
    },
    "cpi_inflation": {
        "label":           "CPI Inflation (Combined)",
        "official_source": "MOSPI — Consumer Price Index",
        "official_url":    "https://mospi.gov.in/consumer-price-indices",
        "verify_url":      "https://tradingeconomics.com/india/inflation-cpi",
        "verify_label":    "TradingEconomics — India CPI Inflation",
        "release_schedule":"Monthly (released ~12th of following month)",
        "max_staleness":   "~6 weeks",
        "fetch_method":    "Auto — MOSPI / TradingEconomics scrape",
        "threshold_note":  "<4% = Bullish | 4–6% = Neutral | >6% = Bearish  ⚠ INVERSE",
        "why_it_matters":  "INVERSE — CPI above RBI 6% ceiling forces rate hikes that compress equity valuations across all sectors simultaneously",
    },
    "unemployment_rate": {
        "label":           "Unemployment Rate (30-day rolling)",
        "official_source": "CMIE — Consumer Pyramids Household Survey",
        "official_url":    "https://unemploymentinindia.cmie.com/",
        "verify_url":      "https://tradingeconomics.com/india/unemployment-rate",
        "verify_label":    "TradingEconomics — India Unemployment",
        "release_schedule":"Monthly (30-day rolling average)",
        "max_staleness":   "~5 weeks",
        "fetch_method":    "Manual — weekly_inputs.json (CMIE paywalled; monthly headline in ET/Mint)",
        "threshold_note":  "<6% = Bullish | 6–8% = Neutral | >8% = Bearish  ⚠ INVERSE",
        "why_it_matters":  "INVERSE lagging — confirms whether expansion is generating employment; rising unemployment at late cycle is an early exit signal",
    },
    "bank_npa_ratio": {
        "label":           "Bank NPA Ratio (Gross)",
        "official_source": "RBI Financial Stability Report (FSR)",
        "official_url":    "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx",
        "verify_url":      "https://tradingeconomics.com/india/non-performing-loans",
        "verify_label":    "TradingEconomics — India Non-Performing Loans",
        "release_schedule":"Semi-annual (June and December)",
        "max_staleness":   "~6 months",
        "fetch_method":    "Manual — weekly_inputs.json (update after June and December RBI FSR)",
        "threshold_note":  "<3% = Bullish | 3–6% = Neutral | >6% = Bearish  ⚠ INVERSE",
        "why_it_matters":  "INVERSE lagging — NPA level determines how aggressively banks can lend; rising NPAs are a leading indicator of credit crunch",
    },
    "current_account_deficit": {
        "label":           "Current Account Deficit (% of GDP)",
        "official_source": "RBI — Balance of Payments Statistics",
        "official_url":    "https://dbie.rbi.org.in/DBIE/dbie.rbi?site=publications#!4",
        "verify_url":      "https://tradingeconomics.com/india/current-account-to-gdp",
        "verify_label":    "TradingEconomics — India Current Account to GDP",
        "release_schedule":"Quarterly (released ~60 days after quarter end)",
        "max_staleness":   "~4 months",
        "fetch_method":    "Auto — RBI / TradingEconomics scrape",
        "threshold_note":  "<2% deficit = Bullish | 2–3% = Neutral | >3% = Bearish  ⚠ INVERSE",
        "why_it_matters":  "INVERSE lagging — wide CAD weakens INR, triggers FII outflows, and forces RBI tightening even during slowdowns",
    },
    "wpi_inflation": {
        "label":           "WPI Inflation (Wholesale Prices)",
        "official_source": "DPIIT — Office of Economic Adviser",
        "official_url":    "https://eaindustry.nic.in/wpi_pressrelease.aspx",
        "verify_url":      "https://tradingeconomics.com/india/producer-prices-change",
        "verify_label":    "TradingEconomics — India Producer Prices",
        "release_schedule":"Monthly (released ~14th of following month)",
        "max_staleness":   "~6 weeks",
        "fetch_method":    "Auto — DPIIT / TradingEconomics scrape",
        "threshold_note":  "<3% = Bullish | 3–6% = Neutral | >6% = Bearish  ⚠ INVERSE",
        "why_it_matters":  "INVERSE lagging — wholesale prices feed into CPI with a 4–6 week lag; a WPI spike is the earliest warning for retail inflation",
    },
}

ORDER = [
    "nifty_6m_change","pmi_manufacturing","repo_rate_trend","credit_growth","housing_starts",
    "gdp_growth","iip_growth","earnings_growth","auto_sales","gst_collections",
    "cpi_inflation","unemployment_rate","bank_npa_ratio","current_account_deficit","wpi_inflation",
]

GROUPS = {
    "nifty_6m_change": ("Leading Indicators",   "50% of composite score — predict turning points 3–6 months ahead", "#1a5276"),
    "gdp_growth":      ("Coincident Indicators", "33% of composite score — confirm the current state of the economy", "#1d6a2e"),
    "cpi_inflation":   ("Lagging Indicators",    "17% of composite score — validate past cycle phases",              "#7d3c0a"),
}

SIGNAL_COLOURS = {
    "Bullish": ("#d4edda", "#1a7f37", "🟢"),
    "Neutral": ("#fff3cd", "#9a7d0a", "🟡"),
    "Bearish": ("#f8d7da", "#c0392b", "🔴"),
    "Unknown": ("#f5f5f5", "#888888", "⚪"),
}


def _classify_signal(key: str, value_str: str) -> str:
    """Replicate Excel IF thresholds exactly."""
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
        return "Unknown"


def _get_group_key(key: str) -> str:
    """Return the group header key for a given indicator key."""
    idx = ORDER.index(key)
    for gk in ["nifty_6m_change", "gdp_growth", "cpi_inflation"]:
        if ORDER.index(gk) <= idx:
            last = gk
    return last


def _indicator_rows_html(indicators: dict) -> str:
    """Section B — compact scorecard table."""
    rows_html = ""
    current_group = ""
    for key in ORDER:
        gk = _get_group_key(key)
        group_label = GROUPS.get(gk, ("","",""))[0]
        if group_label != current_group:
            current_group = group_label
            gdata = GROUPS.get(gk, ("","","#2c3e50"))
            rows_html += (
                f'<tr><td colspan="6" style="background:#f0f4f8;font-weight:bold;'
                f'padding:8px 12px;font-size:12px;color:{gdata[2]};">'
                f'{gdata[0]} — {gdata[1]}</td></tr>'
            )

        ind    = indicators.get(key, {})
        val    = str(ind.get("value","—")) if ind.get("value") is not None else "⚠ MISSING"
        src    = ind.get("source","—")[:45]
        date_s = str(ind.get("data_date","—"))[:20]
        status = ind.get("fetch_status","UNKNOWN")
        notes  = str(ind.get("notes",""))[:60]
        bg     = STATUS_COLOURS.get(status, "#ffffff")
        icon   = "✅" if status == "OK" else "⚠" if status == "ESTIMATED" else "❌"
        label  = VERIFICATION_REGISTRY.get(key, {}).get("label", key)

        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:7px 12px;font-size:13px;">{label}</td>'
            f'<td style="padding:7px 12px;font-size:13px;font-weight:bold;">{val}</td>'
            f'<td style="padding:7px 12px;font-size:12px;">{src}</td>'
            f'<td style="padding:7px 12px;font-size:12px;">{date_s}</td>'
            f'<td style="padding:7px 12px;font-size:12px;">{icon} {status}</td>'
            f'<td style="padding:7px 12px;font-size:11px;color:#555;">{notes}</td>'
            f'</tr>'
        )
    return rows_html


def _verification_table_html(indicators: dict) -> str:
    """Section G — full source verification table with clickable links."""
    html = ""
    current_group = ""

    for key in ORDER:
        reg = VERIFICATION_REGISTRY.get(key, {})
        ind = indicators.get(key, {})

        # Group header
        gk = _get_group_key(key)
        group_label = GROUPS.get(gk, ("","",""))[0]
        if group_label != current_group:
            current_group = group_label
            gdata = GROUPS.get(gk, ("","","#2c3e50"))
            weight = "50%" if "Leading" in gdata[0] else "33%" if "Coincident" in gdata[0] else "17%"
            html += (
                f'<tr><td colspan="6" style="background:{gdata[2]};color:white;'
                f'padding:10px 14px;font-weight:bold;font-size:13px;letter-spacing:0.5px;">'
                f'{gdata[0].upper()} &nbsp;|&nbsp; Weight: {weight} of composite score'
                f' &nbsp;|&nbsp; {gdata[1]}'
                f'</td></tr>'
            )

        # Value and signal
        raw_val     = ind.get("value")
        val_display = str(raw_val) if raw_val is not None else "⚠ MISSING"
        signal      = _classify_signal(key, str(raw_val)) if raw_val is not None else "Unknown"
        sig_bg, sig_color, sig_icon = SIGNAL_COLOURS.get(signal, ("#f5f5f5","#888","⚪"))

        # Fetch method badge
        fm = reg.get("fetch_method", "")
        if "manual" in fm.lower():
            fetch_icon = "📝 Manual"
            fetch_bg   = "#e8f4fd"
        elif ind.get("is_estimated"):
            fetch_icon = "⚠ Estimated"
            fetch_bg   = "#fff3cd"
        else:
            fetch_icon = "✅ Auto"
            fetch_bg   = "#d4edda"

        label    = reg.get("label", key)
        why      = reg.get("why_it_matters", "—")
        thresh   = reg.get("threshold_note", "—")
        off_src  = reg.get("official_source", "—")
        off_url  = reg.get("official_url", "#")
        ver_url  = reg.get("verify_url", "#")
        ver_lbl  = reg.get("verify_label", "Cross-check")
        schedule = reg.get("release_schedule", "—")
        stale    = reg.get("max_staleness", "—")
        fm_short = fm[:65]

        html += f"""
        <tr style="border-bottom:2px solid #e8ecf0;">
          <td style="padding:11px 12px;vertical-align:top;min-width:155px;">
            <div style="font-weight:bold;font-size:13px;color:#2c3e50;">{label}</div>
            <div style="font-size:11px;color:#666;margin-top:4px;line-height:1.45;">{why}</div>
          </td>
          <td style="padding:11px 12px;vertical-align:top;text-align:center;min-width:95px;">
            <div style="font-size:17px;font-weight:bold;color:#2c3e50;">{val_display}</div>
            <div style="margin-top:5px;padding:3px 10px;border-radius:12px;
                background:{sig_bg};color:{sig_color};font-size:12px;font-weight:bold;
                display:inline-block;">{sig_icon} {signal}</div>
          </td>
          <td style="padding:11px 12px;vertical-align:top;min-width:185px;">
            <div style="font-size:11px;font-weight:bold;color:#555;margin-bottom:4px;">THRESHOLD (Excel formula)</div>
            <div style="font-size:11px;color:#333;line-height:1.55;">{thresh}</div>
          </td>
          <td style="padding:11px 12px;vertical-align:top;min-width:175px;">
            <div style="font-size:11px;font-weight:bold;color:#555;margin-bottom:4px;">OFFICIAL SOURCE</div>
            <div style="font-size:12px;margin-bottom:7px;">
              <a href="{off_url}" style="color:#1a5276;text-decoration:none;font-weight:bold;"
                 target="_blank">🔗 {off_src}</a>
            </div>
            <div style="font-size:11px;font-weight:bold;color:#555;margin-bottom:4px;">CROSS-CHECK</div>
            <div style="font-size:12px;">
              <a href="{ver_url}" style="color:#117a65;text-decoration:none;"
                 target="_blank">🔍 {ver_lbl}</a>
            </div>
          </td>
          <td style="padding:11px 12px;vertical-align:top;min-width:130px;">
            <div style="font-size:11px;font-weight:bold;color:#555;margin-bottom:4px;">RELEASE SCHEDULE</div>
            <div style="font-size:12px;color:#333;margin-bottom:8px;">{schedule}</div>
            <div style="font-size:11px;font-weight:bold;color:#555;margin-bottom:4px;">MAX DATA AGE</div>
            <div style="font-size:12px;color:#e67e22;font-weight:bold;">{stale}</div>
          </td>
          <td style="padding:11px 12px;vertical-align:top;min-width:140px;">
            <div style="font-size:11px;font-weight:bold;color:#555;margin-bottom:4px;">HOW FETCHED</div>
            <div style="padding:3px 8px;border-radius:4px;background:{fetch_bg};
                font-size:11px;font-weight:bold;display:inline-block;margin-bottom:6px;">{fetch_icon}</div>
            <div style="font-size:11px;color:#555;line-height:1.4;">{fm_short}</div>
          </td>
        </tr>"""

    return html


def build_html_email(cycle_result: dict, indicators: dict, sector_recs: dict,
                     run_date: str = None) -> str:
    if run_date is None:
        run_date = datetime.datetime.now().strftime("%d %b %Y %H:%M")

    phase     = cycle_result.get("phase", "UNKNOWN")
    score     = cycle_result.get("composite_score", 0)
    momentum  = cycle_result.get("momentum", "—")
    conf      = cycle_result.get("confidence", "—")
    delta     = cycle_result.get("score_delta")
    delta_str = f"{delta:+.4f}" if delta is not None else "N/A"
    rebalance = "🔔 YES — Review allocations" if cycle_result.get("rebalance_flag") else "No"
    phase_changed = cycle_result.get("phase_changed", False)
    prior_phase   = cycle_result.get("prior_phase", "—")

    phase_colour = PHASE_COLOURS_HEX.get(phase, "#2c3e50")
    strategy     = sector_recs.get("strategy", {})
    etf_recs     = sector_recs.get("etf_recs", {})
    action       = strategy.get("action", "—")

    live_count = cycle_result.get("live_count", 0)
    est_count  = cycle_result.get("estimated_count", 0)
    man_count  = cycle_result.get("manual_count", 0)
    auto_ind   = sum(1 for k in ORDER
                     if "manual" not in VERIFICATION_REGISTRY.get(k,{}).get("fetch_method","").lower())
    manual_ind = 15 - auto_ind

    # ETF rows
    etf_rows = ""
    TAG_COLOURS   = {"BUY":"#1a7f37","WATCHLIST":"#b7950b","AVOID":"#c0392b"}
    STANCE_LABELS = {"OW":"Overweight","N":"Neutral","UW":"Underweight"}
    for ticker, info in etf_recs.items():
        tag_c    = TAG_COLOURS.get(info.get("tag",""), "#555")
        rsi_s    = f"{info['rsi']:.0f}" if info.get("rsi") else "N/A"
        mom_s    = f"{info['momentum_4w']:+.1f}%" if info.get("momentum_4w") is not None else "N/A"
        price_s  = f"&#8377;{info['price']:,.0f}" if info.get("price") else "N/A"
        stance_s = STANCE_LABELS.get(info.get("stance","N"), "Neutral")
        vol_s    = f"{info['vol_annual']:.0f}%" if info.get("vol_annual") else "N/A"
        etf_rows += (
            f'<tr>'
            f'<td style="padding:7px;">{info.get("name","")}</td>'
            f'<td style="padding:7px;font-family:monospace;">{ticker}</td>'
            f'<td style="padding:7px;">{stance_s}</td>'
            f'<td style="padding:7px;font-weight:bold;color:{tag_c};">{info.get("tag","")}</td>'
            f'<td style="padding:7px;">{price_s}</td>'
            f'<td style="padding:7px;">{rsi_s}</td>'
            f'<td style="padding:7px;">{mom_s}</td>'
            f'<td style="padding:7px;">{info.get("ma_signal","N/A")}</td>'
            f'<td style="padding:7px;">{vol_s}</td>'
            f'</tr>'
        )

    ow_sectors = ", ".join(strategy.get("overweight", []))
    uw_sectors = ", ".join(strategy.get("underweight", []))

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body  {{ font-family:Arial,sans-serif; font-size:14px; color:#2c3e50; max-width:980px; margin:auto; padding:20px; }}
  h3    {{ border-left:4px solid {phase_colour}; padding-left:10px; margin-top:28px; color:#2c3e50; }}
  table {{ border-collapse:collapse; width:100%; margin-bottom:20px; }}
  th    {{ background:{phase_colour}; color:white; padding:9px 12px; font-size:13px; text-align:left; }}
  td    {{ border-bottom:1px solid #e0e0e0; vertical-align:middle; }}
  a     {{ color:#1a5276; }}
  .phase-badge {{ background:{phase_colour}; color:white; padding:8px 20px; border-radius:6px;
                  font-size:18px; font-weight:bold; display:inline-block; }}
  .action-box  {{ background:#fef9e7; border-left:5px solid #f39c12; padding:15px 20px;
                  font-size:15px; margin:15px 0; border-radius:4px; }}
</style>
</head><body>

<p style="color:#888;font-size:12px;">India Macro Cycle System | {run_date}</p>
<h1 style="color:{phase_colour};">&#127470;&#127475; India Business Cycle Report</h1>

<!-- ════ A: CYCLE SUMMARY ════ -->
<h3>A &#8212; Business Cycle Summary</h3>
<table>
  <tr><th>Metric</th><th>Value</th><th>Detail</th></tr>
  <tr><td>Cycle Phase</td>
      <td><span class="phase-badge">{phase}</span></td>
      <td>{strategy.get("market_outlook","")}</td></tr>
  <tr><td>Composite Score</td>
      <td><b>{score:.4f}</b> ({score*100:.1f}%)</td>
      <td>Range: 0.000 (all bearish) &#8594; 1.000 (all bullish)</td></tr>
  <tr><td>Score Momentum</td>
      <td><b>{momentum}</b></td>
      <td>Week-on-week &#916;: {delta_str}</td></tr>
  <tr><td>Confidence</td>
      <td><b>{conf}</b></td>
      <td>Live: {live_count} | Estimated: {est_count} | Manual: {man_count}</td></tr>
  <tr><td>Rebalance Signal</td>
      <td><b>{rebalance}</b></td>
      <td>{"&#9888; Phase changed from " + str(prior_phase) if phase_changed else "No phase change this week"}</td></tr>
  <tr><td>Historical Precedent</td>
      <td colspan="2">{strategy.get("model_years","&#8212;")}</td></tr>
</table>

<!-- ════ B: INPUT SCORECARD ════ -->
<h3>B &#8212; Full Input Scorecard (All 15 Indicators)</h3>
<p style="font-size:12px;">
  &#9989; Green = Live official data &nbsp;|&nbsp;
  &#9888; Yellow = Estimated / scraped &nbsp;|&nbsp;
  &#10060; Red = Manual entry required
</p>
<table>
  <tr><th>Indicator</th><th>Value</th><th>Source</th><th>Data Date</th><th>Status</th><th>Notes</th></tr>
  {_indicator_rows_html(indicators)}
</table>

<!-- ════ C: MACRO INTERPRETATION ════ -->
<h3>C &#8212; Macro Interpretation</h3>
<table>
  <tr><th colspan="2">Factor</th></tr>
  <tr><td>&#128273; Key Driver 1</td><td>GDP growth trajectory and IIP momentum setting the tone for capex and earnings outlook</td></tr>
  <tr><td>&#128273; Key Driver 2</td><td>RBI monetary stance &#8212; rate direction directly impacts credit growth, banking NIMs and real-estate demand</td></tr>
  <tr><td>&#128273; Key Driver 3</td><td>PMI and auto sales as high-frequency demand signals confirming or denying the cycle thesis</td></tr>
  <tr><td>&#9888; Risk 1</td><td>CPI / WPI inflation re-acceleration forcing premature rate hikes &#8212; most lethal to current cyclical trade</td></tr>
  <tr><td>&#9888; Risk 2</td><td>FII outflows driven by global risk-off or INR depreciation &#8212; watch monthly net equity flows</td></tr>
  <tr><td>&#128065; Watch 1</td><td>Bank credit growth: sustained &gt;15% confirms Early Expansion thesis; &lt;12% signals caution</td></tr>
  <tr><td>&#128065; Watch 2</td><td>Composite score momentum over 3 consecutive weeks before committing to major rebalance</td></tr>
</table>

<!-- ════ D: SECTOR STRATEGY ════ -->
<h3>D &#8212; Sector Strategy for {phase}</h3>
<table>
  <tr><th>Stance</th><th>Sectors</th></tr>
  <tr style="background:#d4edda;"><td><b>&#11014; Overweight</b></td><td>{ow_sectors}</td></tr>
  <tr style="background:#fff3cd;"><td><b>&#10145; Neutral</b></td><td>{", ".join(strategy.get("neutral",[]))}</td></tr>
  <tr style="background:#f8d7da;"><td><b>&#11015; Underweight</b></td><td>{uw_sectors}</td></tr>
</table>

<!-- ════ E: ETF RECOMMENDATIONS ════ -->
<h3>E &#8212; NSE Sectoral ETF Recommendations</h3>
<p style="font-size:12px;">Scoring: Cycle fit (40%) + Momentum (35%) + MA/RSI technical (25%)</p>
<table>
  <tr><th>Name</th><th>Ticker</th><th>Cycle Stance</th><th>Tag</th>
      <th>Price</th><th>RSI(14)</th><th>4W Mom</th><th>MA Cross</th><th>Ann Vol</th></tr>
  {etf_rows}
</table>

<!-- ════ F: ACTION ════ -->
<h3>F &#8212; This Week's Action</h3>
<div class="action-box">
  &#9889; <b>THIS WEEK'S ACTION:</b><br><br>
  {action}
</div>

<!-- ════ G: SOURCE VERIFICATION TABLE (NEW) ════ -->
<h3>G &#8212; Source Verification &amp; Data Authenticity</h3>
<p style="font-size:12px;color:#555;margin-bottom:10px;">
  Use this table to verify every input value before acting on the report.
  Each row shows the exact value used in the composite score calculation, the signal it triggered,
  the Excel threshold formula applied, the official government source with a direct link,
  a second independent cross-check source, how fresh the data is, and how the system obtained it.
  Click any &#128279; link to open the source page directly.
</p>
<p style="font-size:12px;margin-bottom:14px;">
  <span style="background:#d4edda;padding:3px 8px;border-radius:4px;font-weight:bold;">&#9989; Auto</span>
  &nbsp;Fetched automatically from free official source &nbsp;&#124;&nbsp;
  <span style="background:#e8f4fd;padding:3px 8px;border-radius:4px;font-weight:bold;">&#128221; Manual</span>
  &nbsp;You entered this in weekly_inputs.json &nbsp;&#124;&nbsp;
  <span style="background:#fff3cd;padding:3px 8px;border-radius:4px;font-weight:bold;">&#9888; Estimated</span>
  &nbsp;Scraped from secondary source &#8212; cross-verify before trusting
</p>
<table style="font-size:12px;">
  <tr>
    <th style="min-width:150px;">Indicator &amp; Why It Matters</th>
    <th style="min-width:90px;">Value &amp; Signal</th>
    <th style="min-width:175px;">Threshold (Excel IF formula)</th>
    <th style="min-width:165px;">Official Source &amp; Cross-Check</th>
    <th style="min-width:125px;">Release &amp; Max Age</th>
    <th style="min-width:135px;">How Fetched</th>
  </tr>
  {_verification_table_html(indicators)}
</table>

<div style="background:#f0f4f8;border-left:4px solid #2c3e50;padding:12px 16px;
     margin:16px 0;border-radius:4px;font-size:12px;color:#444;line-height:1.6;">
  <b>Data Authenticity Summary:</b>
  &nbsp;&#9989; {auto_ind} indicators fetched automatically from official free sources
  &nbsp;&#124;&nbsp;
  &#128221; {manual_ind} indicators entered manually from paywalled or quarterly sources
  &nbsp;&#124;&nbsp;
  All signal thresholds match the exact IF formulas in your Excel sheet (cells C/D/E, rows 8&#8211;28)
  &nbsp;&#124;&nbsp;
  Composite score formula: =SUM(I8:I12, I16:I20, I24:I28) &#8212; identical in Excel and Python
</div>

<hr>
<p style="font-size:11px;color:#999;">
  Generated by India Macro Cycle System on {run_date}.<br>
  Data sources: MOSPI, RBI, Finance Ministry, SIAM/FADA, NSE India via yfinance. Free official sources only.<br>
  This report is for personal investment research only &#8212; not financial advice.
  Always cross-verify values using the Source Verification table above before making portfolio decisions.
</p>
</body></html>"""

    return html


def send_email(html_body: str, cycle_result: dict, gmail_user: str,
               gmail_pass: str, recipient: str) -> bool:
    phase    = cycle_result.get("phase", "UNKNOWN")
    score    = cycle_result.get("composite_score", 0)
    momentum = cycle_result.get("momentum", "—")
    run_date = datetime.datetime.now().strftime("%d-%b-%Y")
    subject  = f"[Macro] {phase} | Score: {score:.3f} | {momentum} | {run_date}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipient, msg.as_string())
        logger.info(f"  Email sent to {recipient}: {subject}")
        return True
    except Exception as e:
        logger.error(f"  Email failed: {e}")
        return False


def preview_and_send(cycle_result: dict, indicators: dict, sector_recs: dict,
                     gmail_user: str, gmail_pass: str, recipient: str,
                     preview_path: Path = None) -> None:
    from colorama import Fore, Style

    run_date = datetime.datetime.now().strftime("%d %b %Y %H:%M")
    html     = build_html_email(cycle_result, indicators, sector_recs, run_date)

    if preview_path:
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  HTML preview saved: {preview_path}")

    print()
    print(f"  Email subject: [Macro] {cycle_result.get('phase')} | "
          f"Score: {cycle_result.get('composite_score',0):.3f} | "
          f"{cycle_result.get('momentum')} | "
          f"{datetime.datetime.now().strftime('%d-%b-%Y')}")
    print(f"  Recipient: {recipient}")
    print()
    choice = input("  Send email now? [Y/N]: ").strip().upper()

    if choice == "Y":
        if not gmail_user or gmail_user.startswith("your@"):
            print(Fore.RED + "  Gmail credentials not configured in config.py." + Style.RESET_ALL)
            return
        print("  Sending...")
        ok = send_email(html, cycle_result, gmail_user, gmail_pass, recipient)
        if ok:
            print(Fore.GREEN + "  Email sent successfully." + Style.RESET_ALL)
        else:
            print(Fore.RED + "  Email failed — check logs/macro_run.log for details." + Style.RESET_ALL)
    else:
        print("  Email skipped.")
