# 🇮🇳 India Macro Cycle System

Automated weekly business cycle tracker for India using the **Merrill Lynch Investment Clock**.  
Runs entirely on **GitHub Actions** — no local computer required after setup.

---

## How It Works

```
Every Sunday evening
  └── You edit manual_inputs/weekly_inputs.json (4 values)
      └── Commit & push to GitHub  (or edit directly on github.com)

Every Monday 08:00 IST (02:30 UTC) — automatically:
  ├── Fetches 11 indicators from free official sources
  ├── Reads your 4 manual values from the JSON file
  ├── Computes composite score (same formula as your Excel)
  ├── Determines cycle phase
  ├── Fetches ETF data + generates sector recommendations
  ├── Sends you a full HTML email report
  ├── Commits updated history/macro_history.csv to the repo
  └── Uploads email HTML + log as downloadable artifacts
```

---

## One-Time Setup (~15 minutes)

### Step 1 — Create a private GitHub repository

1. Go to [github.com](https://github.com) → **New repository**
2. Name it: `india-macro-cycle`
3. Set to **Private**
4. Click **Create repository**

### Step 2 — Push this code

```cmd
cd macro-cycle-system
git init
git add .
git commit -m "Initial setup"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/india-macro-cycle.git
git push -u origin main
```

Or drag-and-drop the folder contents using GitHub Desktop.

### Step 3 — Add 3 GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Value |
|---|---|
| `GMAIL_USER` | Your Gmail address (`you@gmail.com`) |
| `GMAIL_PASS` | Your Gmail **App Password** (16 chars — see below) |
| `RECIPIENT_EMAIL` | Where to deliver the report |

**How to get a Gmail App Password:**
1. [myaccount.google.com/security](https://myaccount.google.com/security) → enable 2-Step Verification
2. Search **App Passwords** → create one for Mail → copy the 16-character code
3. Paste it as `GMAIL_PASS` — this is NOT your regular Gmail password

### Step 4 — Test the workflow

1. Go to **Actions** tab in your repo
2. Click **India Macro Cycle — Weekly Monday Run**
3. Click **Run workflow** → **Run workflow**
4. Wait ~3 minutes → check your email

---

## Your Weekly Routine (Every Sunday Evening)

Edit `manual_inputs/weekly_inputs.json` — fill in 4 values:

```json
{
  "pmi_manufacturing":  { "value": 56.4,    "last_updated": "2026-04-13" },
  "housing_starts":     { "value": "Rising", "last_updated": "2026-04-13" },
  "earnings_growth":    { "value": 18.5,    "last_updated": "2026-04-13" },
  "unemployment_rate":  { "value": 7.8,     "last_updated": "2026-04-13" }
}
```

**Option A — Edit on GitHub.com (easiest, no Git needed):**
1. Go to `manual_inputs/weekly_inputs.json` in your repo
2. Click the pencil ✏️ icon → edit values → **Commit changes**

**Option B — Edit locally and push:**
```cmd
git add manual_inputs/weekly_inputs.json
git commit -m "Inputs for week of 14-Apr-2026"
git push
```

### Where to find each value (free sources)

| Indicator | Free Source | When Released |
|---|---|---|
| **PMI Manufacturing** | Business Standard / ET publish it free. Search *"India Manufacturing PMI April 2026"* | 1st business day of month |
| **Housing Starts** | Anarock press release or PropEquity. Enter `Rising` / `Stable` / `Falling` | Quarterly |
| **Earnings Growth** | Motilal Oswal quarterly earnings PDF, or search *"Nifty PAT growth Q4FY26"* | After results season |
| **Unemployment Rate** | ET/Mint publish CMIE headline. Search *"CMIE unemployment rate March 2026"* | Mid-month |

---

## What Happens If You Forget

If any value is still `null` in the JSON file, the workflow **fails immediately** with a clear error:

```
❌ Manual input missing for: pmi_manufacturing
   Edit manual_inputs/weekly_inputs.json and set a value before Monday run.
```

Fix it on GitHub.com, then go to **Actions** → **Run workflow** to re-run.

---

## Viewing the Report

**Email** — delivered Monday ~8:00 AM IST  
Subject: `[Macro] EARLY EXPANSION | Score: 0.723 | Rising | 14-Apr-2026`

**Artifact (HTML file):**
1. Actions tab → latest run → scroll to **Artifacts**
2. Download `macro-report-XXXXX` → open `email_report.html` in browser

**History CSV:**  
`history/macro_history.csv` in your repo — open in Excel to see all weeks side by side.

---

## Manual Trigger Options

Go to **Actions** → **Run workflow** to trigger at any time with these options:

| Option | What it does |
|---|---|
| `dry_run = true` | Runs everything, emails report, but does NOT commit history |
| `skip_email = true` | Runs everything but does NOT send email (report saved as artifact only) |

---

## Indicator Sources

| # | Indicator | Auto/Manual | Source |
|---|---|---|---|
| 1 | Nifty 50 6M Price Change | ✅ Auto | yfinance (NSE) |
| 2 | **PMI Manufacturing** | 📝 Manual JSON | S&P Global (paywalled) |
| 3 | RBI Repo Rate Trend | ✅ Auto | rbi.org.in |
| 4 | Credit Growth YoY | ✅ Auto | RBI DBIE |
| 5 | **Housing Starts** | 📝 Manual JSON | Anarock / PropEquity |
| 6 | GDP Growth | ✅ Auto | MOSPI / data.gov.in |
| 7 | IIP Industrial Production | ✅ Auto | MOSPI |
| 8 | **Corporate Earnings Growth** | 📝 Manual JSON | NSE / MOSL |
| 9 | Auto Sales YoY | ✅ Auto | SIAM / FADA |
| 10 | GST Collections YoY | ✅ Auto | Finance Ministry / PIB |
| 11 | CPI Inflation | ✅ Auto | MOSPI |
| 12 | **Unemployment Rate** | 📝 Manual JSON | CMIE (paywalled) |
| 13 | Bank NPA Ratio | ✅ Auto | RBI FSR |
| 14 | Current Account Deficit | ✅ Auto | RBI / MOSPI |
| 15 | WPI Inflation | ✅ Auto | DPIIT |

---

## Composite Score Formula (mirrors your Excel exactly)

```
Score = Σ (signal × weight)    where signal: Bullish=1.0 | Neutral=0.5 | Bearish=0.0

Leading (B8–B12)    : 0.10 × 5 = 50%
Coincident (B16–B20): 0.067 × 5 = 33%
Lagging (B24–B28)   : 0.033 × 5 = 17%
```

| Score | Phase | Overweight | Underweight |
|---|---|---|---|
| 0.80–1.00 | 🟢 Strong Recovery | Realty, Metal, PSU Bank, Bank, Auto | FMCG, Pharma |
| 0.60–0.80 | 🟢 Early Expansion | Bank, Metal, Auto, Infra, Realty | FMCG, Pharma |
| 0.40–0.60 | 🟡 Mid Cycle | Bank, IT, Auto, Energy | Realty, Healthcare |
| 0.20–0.40 | 🟠 Late Cycle | Energy, FMCG, Pharma, IT | Realty, Auto |
| 0.00–0.20 | 🔴 Contraction | FMCG, Pharma, Healthcare, IT | Bank, Realty, Metal |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Workflow fails: `Manual input missing` | Edit `manual_inputs/weekly_inputs.json`, commit, re-run from Actions tab |
| Email not received | Check spam. Verify `GMAIL_PASS` is the App Password (16 chars), not your main password |
| Workflow runs late | GitHub Actions cron can run up to 15 min late — normal behaviour |
| `ESTIMATED` values in report | Some sources fall back to TradingEconomics. Flagged ⚠ in email — cross-verify if critical |

---

*For personal investment research only — not financial advice.*
