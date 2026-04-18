# ============================================================
#  src/sector_mapper.py
#  Maps cycle phase to sector strategy (from Excel + PPT).
#  Fetches live ETF data: RSI, momentum, MA signals.
#  Produces BUY / WATCHLIST / AVOID tags.
# ============================================================

import logging
import datetime
import sys
from pathlib import Path

logger = logging.getLogger("macro_cycle")

# ── Full sector strategy from PPT + Excel ────────────────────
SECTOR_STRATEGY = {
    "STRONG RECOVERY": {
        "overweight":  ["Nifty Bank / Financials", "Nifty Realty", "Nifty Metal", "Nifty PSU Bank", "Nifty Auto"],
        "neutral":     ["Nifty IT", "Nifty Infra", "Nifty Energy"],
        "underweight": ["Nifty FMCG", "Nifty Pharma", "Nifty Healthcare"],
        "action": "Maximum equity. Overweight beaten-down cyclicals (Realty, Metals, PSU Banks). Start watching for cycle-peak reversal signals.",
        "market_outlook": "Euphoric; highest returns and highest reversal risk",
        "model_years": "2009-10, 2003-04",
    },
    "EARLY EXPANSION": {
        "overweight":  ["Nifty Bank / Financials", "Nifty Metal", "Nifty Auto", "Nifty Infra", "Nifty Realty"],
        "neutral":     ["Nifty IT", "Nifty Energy", "Nifty PSU Bank"],
        "underweight": ["Nifty FMCG", "Nifty Pharma", "Nifty Healthcare"],
        "action": "Aggressively overweight cyclicals. Add mid/small caps in outperforming sectors.",
        "market_outlook": "Strong bull market; +20-40% possible",
        "model_years": "2014-15, 2021-22",
    },
    "MID CYCLE": {
        "overweight":  ["Nifty Bank / Financials", "Nifty IT", "Nifty Auto", "Nifty Energy"],
        "neutral":     ["Nifty Metal", "Nifty Infra", "Nifty PSU Bank"],
        "underweight": ["Nifty Realty", "Nifty Healthcare", "Nifty FMCG"],
        "action": "Balanced allocation. Follow relative-strength signals monthly. Mixed sector performance.",
        "market_outlook": "Steady +10-18% annually",
        "model_years": "2016-17, 2023-24",
    },
    "LATE CYCLE": {
        "overweight":  ["Nifty Energy", "Nifty FMCG", "Nifty Pharma", "Nifty IT"],
        "neutral":     ["Nifty Metal", "Nifty Infra", "Nifty Bank"],
        "underweight": ["Nifty Realty", "Nifty Auto", "Nifty PSU Bank"],
        "action": "Rotate defensive. Reduce beta. Tighten quality. Watch for cycle turn.",
        "market_outlook": "Flat to -10%; high sector dispersion",
        "model_years": "2011-12, 2018-19",
    },
    "CONTRACTION": {
        "overweight":  ["Nifty FMCG", "Nifty Pharma", "Nifty Healthcare", "Nifty IT (large cap)"],
        "neutral":     ["Nifty Energy"],
        "underweight": ["Nifty Bank", "Nifty Realty", "Nifty Metal", "Nifty Auto", "Nifty Infra"],
        "action": "Maximum defensive. Earnings visibility, inelastic demand, dividend yield, Gold.",
        "market_outlook": "Bear market; capital preservation priority",
        "model_years": "2019-20, 2008-09",
    },
}

# ── ETF universe ─────────────────────────────────────────────
ETF_MAP = {
    "BANKBEES.NS":   {"name": "Nifty Bank",      "sector": "Banking"},
    "ITBEES.NS":     {"name": "Nifty IT",         "sector": "IT"},
    "PHARMABEES.NS": {"name": "Nifty Pharma",     "sector": "Pharma"},
    "FMCGBEES.NS":   {"name": "Nifty FMCG",       "sector": "FMCG"},
    "METALBEES.NS":  {"name": "Nifty Metal",      "sector": "Metal"},
    "PSUBNKBEES.NS": {"name": "Nifty PSU Bank",   "sector": "PSU Bank"},
    "INFRABEES.NS":  {"name": "Nifty Infra",      "sector": "Infrastructure"},
    "GOLDBEES.NS":   {"name": "Gold ETF",         "sector": "Gold"},
    "SETFNIF50.NS":  {"name": "Nifty 50",         "sector": "Broad Market"},
}

# Phase → ETF weight stance
PHASE_ETF_STANCE = {
    "STRONG RECOVERY": {
        "BANKBEES.NS":"OW","PSUBNKBEES.NS":"OW","METALBEES.NS":"OW",
        "ITBEES.NS":"N","PHARMABEES.NS":"UW","FMCGBEES.NS":"UW",
        "INFRABEES.NS":"N","GOLDBEES.NS":"UW","SETFNIF50.NS":"OW",
    },
    "EARLY EXPANSION": {
        "BANKBEES.NS":"OW","METALBEES.NS":"OW","INFRABEES.NS":"OW",
        "ITBEES.NS":"N","PHARMABEES.NS":"UW","FMCGBEES.NS":"UW",
        "PSUBNKBEES.NS":"N","GOLDBEES.NS":"UW","SETFNIF50.NS":"OW",
    },
    "MID CYCLE": {
        "BANKBEES.NS":"OW","ITBEES.NS":"OW","PHARMABEES.NS":"N",
        "FMCGBEES.NS":"N","METALBEES.NS":"N","INFRABEES.NS":"N",
        "PSUBNKBEES.NS":"N","GOLDBEES.NS":"UW","SETFNIF50.NS":"OW",
    },
    "LATE CYCLE": {
        "BANKBEES.NS":"UW","ITBEES.NS":"OW","PHARMABEES.NS":"OW",
        "FMCGBEES.NS":"OW","METALBEES.NS":"N","INFRABEES.NS":"UW",
        "PSUBNKBEES.NS":"UW","GOLDBEES.NS":"OW","SETFNIF50.NS":"N",
    },
    "CONTRACTION": {
        "BANKBEES.NS":"UW","ITBEES.NS":"OW","PHARMABEES.NS":"OW",
        "FMCGBEES.NS":"OW","METALBEES.NS":"UW","INFRABEES.NS":"UW",
        "PSUBNKBEES.NS":"UW","GOLDBEES.NS":"OW","SETFNIF50.NS":"UW",
    },
}


def fetch_etf_data(tickers: list) -> dict:
    """Fetch price, RSI(14), 4-week momentum, MA cross for each ETF."""
    results = {}
    try:
        import yfinance as yf
        import numpy as np

        data = yf.download(tickers, period="6mo", interval="1wk",
                           progress=False, auto_adjust=True)["Close"]
        if data.empty:
            raise ValueError("Empty ETF data")

        for ticker in tickers:
            try:
                if ticker not in data.columns:
                    continue
                prices = data[ticker].dropna()
                if len(prices) < 20:
                    continue

                current   = float(prices.iloc[-1])
                w4_ago    = float(prices.iloc[-5])  if len(prices) >= 5  else current
                w13_ago   = float(prices.iloc[-14]) if len(prices) >= 14 else current
                ma50      = float(prices.tail(7).mean())   # ~50d weekly proxy
                ma200     = float(prices.tail(26).mean())  # ~200d weekly proxy

                momentum_4w = round((current - w4_ago)  / w4_ago  * 100, 2)
                momentum_13w= round((current - w13_ago) / w13_ago * 100, 2)

                # RSI(14) weekly
                delta  = prices.diff().dropna()
                gains  = delta.clip(lower=0)
                losses = (-delta).clip(lower=0)
                avg_g  = gains.tail(14).mean()
                avg_l  = losses.tail(14).mean()
                rsi    = round(100 - 100 / (1 + avg_g / avg_l) if avg_l != 0 else 100, 1)

                ma_signal = "Golden Cross" if ma50 > ma200 else "Death Cross"

                # Annualised vol (12-week returns)
                weekly_returns = prices.pct_change().dropna().tail(12)
                vol_annual = round(float(weekly_returns.std() * (52**0.5) * 100), 1)

                results[ticker] = {
                    "price": round(current, 2), "rsi": rsi,
                    "momentum_4w": momentum_4w, "momentum_13w": momentum_13w,
                    "ma_signal": ma_signal, "vol_annual": vol_annual,
                    "ma50": round(ma50, 2), "ma200": round(ma200, 2),
                }
            except Exception as e:
                logger.warning(f"  ETF {ticker}: {e}")
                results[ticker] = {"price": None, "rsi": None, "momentum_4w": None,
                                   "momentum_13w": None, "ma_signal": "N/A", "vol_annual": None}
    except Exception as e:
        logger.error(f"  ETF fetch failed: {e}")
    return results


def _tag_etf(cycle_stance: str, rsi, momentum_4w, ma_signal) -> str:
    """BUY / WATCHLIST / AVOID based on cycle fit + momentum + technical."""
    if cycle_stance == "OW":
        cycle_score = 1.0
    elif cycle_stance == "N":
        cycle_score = 0.5
    else:
        cycle_score = 0.0

    momentum_score = 0.0
    if momentum_4w is not None:
        momentum_score = 1.0 if momentum_4w > 5 else 0.5 if momentum_4w > 0 else 0.0

    tech_score = 0.0
    if ma_signal == "Golden Cross":
        tech_score = 1.0
    elif rsi is not None and 40 <= rsi <= 65:
        tech_score = 0.7
    elif rsi is not None and rsi < 30:
        tech_score = 0.5  # oversold — potential contrarian entry

    composite = cycle_score * 0.40 + momentum_score * 0.35 + tech_score * 0.25

    if composite >= 0.65:  return "BUY"
    if composite >= 0.40:  return "WATCHLIST"
    return "AVOID"


def get_sector_recommendations(phase: str) -> dict:
    """Full sector + ETF recommendation for the given phase."""
    strategy  = SECTOR_STRATEGY.get(phase, SECTOR_STRATEGY["MID CYCLE"])
    stances   = PHASE_ETF_STANCE.get(phase, {})
    tickers   = list(ETF_MAP.keys())

    logger.info(f"  Fetching ETF data for {len(tickers)} tickers...")
    etf_data  = fetch_etf_data(tickers)

    etf_recs = {}
    for ticker in tickers:
        stance  = stances.get(ticker, "N")
        data    = etf_data.get(ticker, {})
        rsi     = data.get("rsi")
        mom     = data.get("momentum_4w")
        ma_sig  = data.get("ma_signal", "N/A")
        tag     = _tag_etf(stance, rsi, mom, ma_sig)
        etf_recs[ticker] = {
            **ETF_MAP[ticker],
            "stance": stance, "tag": tag,
            "price":       data.get("price"),
            "rsi":         rsi,
            "momentum_4w": mom,
            "momentum_13w":data.get("momentum_13w"),
            "ma_signal":   ma_sig,
            "vol_annual":  data.get("vol_annual"),
        }

    return {
        "phase":       phase,
        "strategy":    strategy,
        "etf_recs":    etf_recs,
        "run_date":    datetime.datetime.now().strftime("%Y-%m-%d"),
    }


def print_sector_table(recs: dict) -> None:
    from colorama import Fore, Style

    phase    = recs["phase"]
    strategy = recs["strategy"]
    W = 80

    print()
    print(Fore.CYAN + Style.BRIGHT + "═" * W + Style.RESET_ALL)
    print(Fore.CYAN + Style.BRIGHT + f"  SECTOR STRATEGY — {phase}" + Style.RESET_ALL)
    print(Fore.CYAN + Style.BRIGHT + "═" * W + Style.RESET_ALL)
    print()
    print(Fore.GREEN + f"  OVERWEIGHT  (Favour)  : {', '.join(strategy['overweight'])}" + Style.RESET_ALL)
    print(Fore.YELLOW + f"  NEUTRAL     (Hold)    : {', '.join(strategy['neutral'])}" + Style.RESET_ALL)
    print(Fore.RED +   f"  UNDERWEIGHT (Reduce)  : {', '.join(strategy['underweight'])}" + Style.RESET_ALL)
    print()
    print(f"  Action   : {strategy['action']}")
    print(f"  Outlook  : {strategy['market_outlook']}")
    print(f"  Precedent: {strategy['model_years']}")
    print()

    # ETF table
    TAG_COLOURS = {"BUY": Fore.GREEN, "WATCHLIST": Fore.YELLOW, "AVOID": Fore.RED}
    STANCE_LABELS = {"OW": "Overweight", "N": "Neutral", "UW": "Underweight"}

    print(f"  {'ETF':<16} {'Sector':<15} {'Stance':<14} {'Tag':<10} {'Price':>8} {'RSI':>6} {'4W Mom':>8} {'MA Cross':<15} {'Ann Vol':>8}")
    print(f"  {'─'*16} {'─'*15} {'─'*14} {'─'*10} {'─'*8} {'─'*6} {'─'*8} {'─'*15} {'─'*8}")

    for ticker, info in recs["etf_recs"].items():
        tag_c    = TAG_COLOURS.get(info["tag"], Fore.WHITE)
        tag_str  = tag_c + f"{info['tag']:<10}" + Style.RESET_ALL
        stance_s = STANCE_LABELS.get(info["stance"], "N/A")
        price    = f"₹{info['price']:,.0f}" if info["price"] else "N/A"
        rsi      = f"{info['rsi']:.0f}"   if info["rsi"]   else "N/A"
        mom      = f"{info['momentum_4w']:+.1f}%" if info["momentum_4w"] is not None else "N/A"
        vol      = f"{info['vol_annual']:.0f}%"  if info["vol_annual"]  else "N/A"
        print(f"  {ticker:<16} {info['sector']:<15} {stance_s:<14} {tag_str} {price:>8} {rsi:>6} {mom:>8} {info['ma_signal']:<15} {vol:>8}")

    print()
    print(f"  Scoring: Cycle fit (40%) + Momentum (35%) + MA/RSI Technical (25%)")
    print(f"  {'─'*W}")
