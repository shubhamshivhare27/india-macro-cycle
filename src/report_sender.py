# ============================================================
#  src/report_sender.py
#  Builds an HTML email with all 6 sections and sends
#  via Gmail SMTP. Shows preview before sending.
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


def _indicator_rows_html(indicators: dict) -> str:
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
        "iip_growth":             "IIP Industrial Production",
        "earnings_growth":        "Corporate Earnings Growth",
        "auto_sales":             "Auto Sales YoY",
        "gst_collections":        "GST Collections YoY",
        "cpi_inflation":          "CPI Inflation",
        "unemployment_rate":      "Unemployment Rate",
        "bank_npa_ratio":         "Bank NPA Ratio",
        "current_account_deficit":"Current Account Deficit",
        "wpi_inflation":          "WPI Inflation",
    }
    GROUPS = {
        "nifty_6m_change": "Leading Indicators (50% weight)",
        "gdp_growth":      "Coincident Indicators (33% weight)",
        "cpi_inflation":   "Lagging Indicators (17% weight)",
    }
    rows_html = ""
    current_group = ""
    for key in ORDER:
        if key in GROUPS and GROUPS[key] != current_group:
            current_group = GROUPS[key]
            rows_html += f"""<tr><td colspan="6" style="background:#f0f4f8;font-weight:bold;
                padding:8px 12px;font-size:12px;color:#2c3e50;">{current_group}</td></tr>"""

        ind    = indicators.get(key, {})
        val    = str(ind.get("value","—")) if ind.get("value") is not None else "⚠ MISSING"
        src    = ind.get("source","—")[:45]
        date_s = str(ind.get("data_date","—"))[:20]
        status = ind.get("fetch_status","UNKNOWN")
        notes  = str(ind.get("notes",""))[:60]
        bg     = STATUS_COLOURS.get(status, "#ffffff")
        status_icon = "✅" if status=="OK" else "⚠" if status=="ESTIMATED" else "❌"

        rows_html += f"""
        <tr style="background:{bg}">
          <td style="padding:7px 12px;font-size:13px;">{LABELS.get(key,key)}</td>
          <td style="padding:7px 12px;font-size:13px;font-weight:bold;">{val}</td>
          <td style="padding:7px 12px;font-size:12px;">{src}</td>
          <td style="padding:7px 12px;font-size:12px;">{date_s}</td>
          <td style="padding:7px 12px;font-size:12px;">{status_icon} {status}</td>
          <td style="padding:7px 12px;font-size:11px;color:#555;">{notes}</td>
        </tr>"""
    return rows_html


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
    action       = strategy.get("action","—")

    # Section E: ETF table rows
    etf_rows = ""
    TAG_COLOURS = {"BUY":"#1a7f37","WATCHLIST":"#b7950b","AVOID":"#c0392b"}
    STANCE_LABELS = {"OW":"Overweight","N":"Neutral","UW":"Underweight"}
    for ticker, info in etf_recs.items():
        tag_c   = TAG_COLOURS.get(info.get("tag",""),"#555")
        rsi_s   = f"{info['rsi']:.0f}" if info.get("rsi") else "N/A"
        mom_s   = f"{info['momentum_4w']:+.1f}%" if info.get("momentum_4w") is not None else "N/A"
        price_s = f"₹{info['price']:,.0f}" if info.get("price") else "N/A"
        stance_s = STANCE_LABELS.get(info.get("stance","N"),"Neutral")
        vol_s   = f"{info['vol_annual']:.0f}%" if info.get("vol_annual") else "N/A"
        etf_rows += f"""
        <tr>
          <td style="padding:7px;">{info.get('name','')}</td>
          <td style="padding:7px;font-family:monospace;">{ticker}</td>
          <td style="padding:7px;">{stance_s}</td>
          <td style="padding:7px;font-weight:bold;color:{tag_c};">{info.get('tag','')}</td>
          <td style="padding:7px;">{price_s}</td>
          <td style="padding:7px;">{rsi_s}</td>
          <td style="padding:7px;">{mom_s}</td>
          <td style="padding:7px;">{info.get('ma_signal','N/A')}</td>
          <td style="padding:7px;">{vol_s}</td>
        </tr>"""

    # Macro interpretation bullets
    ow_sectors  = ", ".join(strategy.get("overweight",[]))
    uw_sectors  = ", ".join(strategy.get("underweight",[]))

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size:14px; color:#2c3e50; max-width:900px; margin:auto; padding:20px; }}
  h2   {{ color:{phase_colour}; }}
  h3   {{ border-left:4px solid {phase_colour}; padding-left:10px; }}
  table {{ border-collapse:collapse; width:100%; margin-bottom:20px; }}
  th {{ background:{phase_colour}; color:white; padding:9px 12px; font-size:13px; text-align:left; }}
  td {{ border-bottom:1px solid #e0e0e0; }}
  .phase-badge {{ background:{phase_colour}; color:white; padding:8px 20px; border-radius:6px;
                  font-size:18px; font-weight:bold; display:inline-block; }}
  .action-box  {{ background:#fef9e7; border-left:5px solid #f39c12; padding:15px 20px;
                  font-size:15px; margin:15px 0; border-radius:4px; }}
  .legend      {{ font-size:12px; }}
</style>
</head><body>

<p style="color:#888;font-size:12px;">India Macro Cycle System | {run_date}</p>
<h1 style="color:{phase_colour};">🇮🇳 India Business Cycle Report</h1>

<!-- ════ SECTION A: CYCLE SUMMARY ════ -->
<h3>A — Business Cycle Summary</h3>
<table>
  <tr>
    <th>Metric</th><th>Value</th><th>Detail</th>
  </tr>
  <tr><td>Cycle Phase</td><td><span class="phase-badge">{phase}</span></td>
      <td>{strategy.get('market_outlook','')}</td></tr>
  <tr><td>Composite Score</td><td><b>{score:.4f}</b> ({score*100:.1f}%)</td>
      <td>Range: 0.000 (all bearish) → 1.000 (all bullish)</td></tr>
  <tr><td>Score Momentum</td><td><b>{momentum}</b></td>
      <td>Week-on-week Δ: {delta_str}</td></tr>
  <tr><td>Confidence</td><td><b>{conf}</b></td>
      <td>Live: {cycle_result.get('live_count',0)} | Estimated: {cycle_result.get('estimated_count',0)} | Manual: {cycle_result.get('manual_count',0)}</td></tr>
  <tr><td>Rebalance Signal</td><td><b>{rebalance}</b></td>
      <td>{'⚠ Phase changed from ' + prior_phase if phase_changed else 'No phase change this week'}</td></tr>
  <tr><td>Historical Precedent</td><td colspan="2">{strategy.get('model_years','—')}</td></tr>
</table>

<!-- ════ SECTION B: FULL INPUT SCORECARD ════ -->
<h3>B — Full Input Scorecard (All 15 Indicators)</h3>
<p style="font-size:12px;" class="legend">
  ✅ Green = Live official data | ⚠ Yellow = Estimated / scraped | ❌ Red = Manual entry required
</p>
<table>
  <tr><th>Indicator</th><th>Value</th><th>Source</th><th>Data Date</th><th>Status</th><th>Notes</th></tr>
  {_indicator_rows_html(indicators)}
</table>

<!-- ════ SECTION C: MACRO INTERPRETATION ════ -->
<h3>C — Macro Interpretation</h3>
<table>
  <tr><th colspan="2">Factor</th></tr>
  <tr><td>🔑 Key Driver 1</td><td>GDP growth trajectory and IIP momentum setting the tone for capex and earnings outlook</td></tr>
  <tr><td>🔑 Key Driver 2</td><td>RBI monetary stance — rate direction directly impacts credit growth, banking NIMs and real-estate demand</td></tr>
  <tr><td>🔑 Key Driver 3</td><td>PMI and auto sales as high-frequency demand signals confirming or denying the cycle thesis</td></tr>
  <tr><td>⚠ Risk 1</td><td>CPI / WPI inflation re-acceleration forcing premature rate hikes — most lethal to current cyclical trade</td></tr>
  <tr><td>⚠ Risk 2</td><td>FII outflows driven by global risk-off or INR depreciation — watch monthly net equity flows</td></tr>
  <tr><td>👁 Watch 1</td><td>Bank credit growth: sustained >15% confirms Early Expansion thesis; &lt;12% signals caution</td></tr>
  <tr><td>👁 Watch 2</td><td>Composite score momentum over 3 consecutive weeks before committing to major rebalance</td></tr>
</table>

<!-- ════ SECTION D: SECTOR STRATEGY ════ -->
<h3>D — Sector Strategy for {phase}</h3>
<table>
  <tr><th>Stance</th><th>Sectors</th></tr>
  <tr style="background:#d4edda;"><td><b>⬆ Overweight</b></td><td>{ow_sectors}</td></tr>
  <tr style="background:#fff3cd;"><td><b>➡ Neutral</b></td><td>{', '.join(strategy.get('neutral',[]))}</td></tr>
  <tr style="background:#f8d7da;"><td><b>⬇ Underweight</b></td><td>{uw_sectors}</td></tr>
</table>

<!-- ════ SECTION E: ETF RECOMMENDATIONS ════ -->
<h3>E — NSE Sectoral ETF Recommendations</h3>
<p style="font-size:12px;">Scoring: Cycle fit (40%) + Momentum (35%) + MA/RSI technical (25%)</p>
<table>
  <tr><th>Name</th><th>Ticker</th><th>Cycle Stance</th><th>Tag</th><th>Price</th>
      <th>RSI(14)</th><th>4W Mom</th><th>MA Cross</th><th>Ann Vol</th></tr>
  {etf_rows}
</table>

<!-- ════ SECTION F: ACTION ════ -->
<h3>F — This Week's Action</h3>
<div class="action-box">
  ⚡ <b>THIS WEEK'S ACTION:</b><br><br>
  {action}
</div>

<hr>
<p style="font-size:11px;color:#999;">
  Generated by India Macro Cycle System on {run_date}.<br>
  Data sources: MOSPI, RBI, Finance Ministry, SIAM/FADA, yfinance. Free official sources only.<br>
  This report is for personal investment research only — not financial advice.
  Always cross-verify values before making portfolio decisions.
</p>
</body></html>"""

    return html


def send_email(html_body: str, cycle_result: dict, gmail_user: str,
               gmail_pass: str, recipient: str) -> bool:
    phase     = cycle_result.get("phase", "UNKNOWN")
    score     = cycle_result.get("composite_score", 0)
    momentum  = cycle_result.get("momentum", "—")
    run_date  = datetime.datetime.now().strftime("%d-%b-%Y")
    subject   = f"[Macro] {phase} | Score: {score:.3f} | {momentum} | {run_date}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipient, msg.as_string())
        logger.info(f"  ✅ Email sent to {recipient}: {subject}")
        return True
    except Exception as e:
        logger.error(f"  ❌ Email failed: {e}")
        return False


def preview_and_send(cycle_result: dict, indicators: dict, sector_recs: dict,
                     gmail_user: str, gmail_pass: str, recipient: str,
                     preview_path: Path = None) -> None:
    from colorama import Fore, Style

    run_date = datetime.datetime.now().strftime("%d %b %Y %H:%M")
    html     = build_html_email(cycle_result, indicators, sector_recs, run_date)

    # Save preview HTML
    if preview_path:
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  HTML preview saved: {preview_path}")

    print()
    print(f"  Email subject: [Macro] {cycle_result.get('phase')} | Score: {cycle_result.get('composite_score',0):.3f} | {cycle_result.get('momentum')} | {datetime.datetime.now().strftime('%d-%b-%Y')}")
    print(f"  Recipient:     {recipient}")
    print()
    choice = input("  Send email now? [Y/N]: ").strip().upper()

    if choice == "Y":
        if not gmail_user or gmail_user.startswith("your@"):
            print(Fore.RED + "  ❌ Gmail credentials not configured in config.py. Skipping email." + Style.RESET_ALL)
            return
        print("  Sending...")
        ok = send_email(html, cycle_result, gmail_user, gmail_pass, recipient)
        if ok:
            print(Fore.GREEN + "  ✅ Email sent successfully." + Style.RESET_ALL)
        else:
            print(Fore.RED + "  ❌ Email failed — check logs/macro_run.log for details." + Style.RESET_ALL)
    else:
        print("  Email skipped.")
