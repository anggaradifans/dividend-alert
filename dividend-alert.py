import yfinance as yf
import subprocess

# ============================================================
# WATCHLIST: High Dividend index constituents + notable payers
# ============================================================
TICKERS = [
    "PTBA.JK", "ITMG.JK", "ADRO.JK", "UNTR.JK", "BSSR.JK", "HEXA.JK",
    "MPMX.JK", "TOTL.JK", "DMAS.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK",
    "BJBR.JK", "BJTM.JK", "ASII.JK", "TLKM.JK", "INDF.JK", "ICBP.JK",
    "PGAS.JK", "HMSP.JK", "GGRM.JK", "INDS.JK", "KDSI.JK", "LPPF.JK",
    "BBCA.JK", "INDY.JK", "HRUM.JK", "UNVR.JK", "SIDO.JK", "NELY.JK",
    "BNGA.JK", "NISP.JK", "RALS.JK", "SMSM.JK", "LPKR.JK", "POWR.JK",
    "IPCM.JK", "AMOR.JK", "TPMA.JK", "AUTO.JK", "MSTI.JK", "SPTO.JK",
    "BAYU.JK", "MARK.JK", "TOTO.JK", "IPCC.JK", "AKRA.JK", "AADI.JK", "ACES.JK",
]

THRESHOLD = 8.0  # minimum yield % to flag

# ============================================================
# TARGET ALLOCATIONS (TIERED)
# ============================================================
TARGET_CORE_ALLOCATION = 10_000_000      # For stable, blue-chip companies
TARGET_CYCLICAL_ALLOCATION = 10_000_000  # For commodity-based, cyclical companies
TARGET_DEFAULT_ALLOCATION = 10_000_000   # For others

# Define which stocks belong to which tier (without .JK suffix)
CORE_STOCKS = {"BBCA", "BMRI", "BBRI", "BBNI", "TLKM", "ASII", "ICBP", "INDF", "UNVR", "CPIN"}
CYCLICAL_STOCKS = {"ADRO", "PTBA", "ITMG", "UNTR", "BSSR", "INDY", "HRUM", "PGAS", "MEDC", "HEXA", "MPMX",
                   "AADI", "AUTO", "TPMA", "IPCM", "IPCC", "ACES"}

# Banks are naturally high-DER; use relaxed threshold for them
BANKING_STOCKS = {"BBCA", "BMRI", "BBRI", "BBNI", "BNGA", "NISP", "BJBR", "BJTM"}

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_target_allocation(symbol):
    """Return the target Rp allocation based on stock's tier."""
    if symbol in CORE_STOCKS:
        return TARGET_CORE_ALLOCATION
    elif symbol in CYCLICAL_STOCKS:
        return TARGET_CYCLICAL_ALLOCATION
    return TARGET_DEFAULT_ALLOCATION


# ============================================================
# MY PORTFOLIO: Stocks you currently own
# ============================================================

# Format:  "TICKER.JK": { "lots": <total lots>, "avg_price": <avg buy price in Rp> }
# 1 lot = 100 shares (IDX standard)
#
# *** EDIT THIS SECTION with your actual holdings ***
MY_PORTFOLIO = {
    "ADRO.JK":  {"lots": 4,  "avg_price": 2_233},
    "BBCA.JK":  {"lots": 35, "avg_price": 7_911},
    "BBRI.JK":  {"lots": 10, "avg_price": 3_371},
    "BMRI.JK":  {"lots": 30, "avg_price": 4_846},
    "BNGA.JK":  {"lots": 15, "avg_price": 1_846},
    "DMAS.JK":  {"lots": 60, "avg_price": 140},
    "LPPF.JK":  {"lots": 10, "avg_price": 1_782},
    "SMSM.JK":  {"lots": 5,  "avg_price": 1_742},
    "UNVR.JK":  {"lots": 27, "avg_price": 2_227},
}

SHARES_PER_LOT = 100


# ============================================================
# Data fetching
# ============================================================
# For IDX stocks, cash payment is typically 25–45 days after the ex-dividend date.
# We apply this offset to convert historical ex-dates into approximate payment months.
PAYMENT_OFFSET_DAYS = 30


def _extract_payment_months(dividends, years=3):
    """Return the set of months (1–12) when dividends were approximately *received*.

    yfinance only exposes historical ex-dividend dates for IDX stocks.
    We shift each ex-date forward by PAYMENT_OFFSET_DAYS to estimate the
    month the cash actually arrives in the investor's account.
    """
    try:
        if dividends is None or dividends.empty:
            return set()
        from datetime import datetime, timezone, timedelta
        offset = timedelta(days=PAYMENT_OFFSET_DAYS)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=years * 365)
        try:
            recent = dividends[dividends.index >= cutoff]
        except TypeError:
            recent = dividends[dividends.index >= cutoff.replace(tzinfo=None)]
        if recent.empty:
            recent = dividends  # fallback to all available history
        payment_months = set()
        for ex_date in recent.index:
            try:
                if hasattr(ex_date, 'tzinfo') and ex_date.tzinfo is None:
                    ex_date = ex_date.replace(tzinfo=timezone.utc)
                payment_months.add((ex_date + offset).month)
            except Exception:
                continue
        return payment_months
    except Exception:
        return set()


def fetch_stock_info(ticker_symbol):
    """Fetch stock info and dividend history from yfinance. Returns dict or None on error."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        payment_months = _extract_payment_months(ticker.dividends)
        return {
            "symbol": ticker_symbol.replace(".JK", ""),
            "name": info.get("shortName", ticker_symbol),
            "yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "current_price": info.get("currentPrice", 0) or 0,
            "target_price": info.get("targetMeanPrice", 0) or 0,
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0) or 0,
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0) or 0,
            # --- Financial Quality Indicators ---
            "payout_ratio": info.get("payoutRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "operating_cashflow": info.get("operatingCashflow"),
            "trailing_eps": info.get("trailingEps"),
            "five_year_avg_yield": info.get("fiveYearAvgDividendYield"),
            "sector": info.get("sector", ""),
            # --- Dividend Dates ---
            "ex_dividend_date": info.get("exDividendDate"),
            "last_dividend_date": info.get("lastDividendDate"),
            # --- Dividend Calendar ---
            "payment_months": payment_months,   # approx payment months (ex-date + ~30 days)
        }
    except Exception:
        return None


# ============================================================
# Quality scoring (pure functions – no I/O)
# ============================================================
def compute_quality_score(stock_info):
    """Score a stock 0-10 based on dividend quality criteria.

    Criteria                            Max pts
    ─────────────────────────────────────────────
    1. Dividend Yield in healthy range      2
    2. Payout Ratio 40-70%                 2
    3. Positive Operating Cash Flow        2
    4. Debt-to-Equity reasonable           2
    5. Positive EPS (profitable)           1
    6. 5-Year Avg Yield (consistency)      1
    ─────────────────────────────────────────────
    Total                                 10

    Returns: (score, max_score, details, flags)
    - details: list of per-criterion verdict strings
    - flags:   list of critical warning strings
    """
    score = 0
    max_score = 10
    details = []
    flags = []

    div_yield    = (stock_info.get("yield") or 0) * 1  # already in percent from yfinance × 100-ish? no, it's 0.xx
    # yfinance dividendYield is e.g. 0.085 for 8.5% — normalise
    div_yield_pct = (stock_info.get("yield") or 0) * 100 if (stock_info.get("yield") or 0) < 1 else (stock_info.get("yield") or 0)
    payout_ratio   = stock_info.get("payout_ratio")
    operating_cf   = stock_info.get("operating_cashflow")
    der            = stock_info.get("debt_to_equity")
    eps            = stock_info.get("trailing_eps")
    five_yr_yield  = stock_info.get("five_year_avg_yield")
    symbol         = stock_info.get("symbol", "")
    is_bank        = symbol in BANKING_STOCKS

    # 1. Dividend Yield (2 pts)
    if 3.0 <= div_yield_pct <= 15.0:
        score += 2
        details.append(f"✅ Yield {div_yield_pct:.1f}% (healthy range 3–15%)")
    elif div_yield_pct > 15.0:
        flags.append(f"⚠️  DIVIDEND TRAP RISK — yield {div_yield_pct:.1f}% is suspiciously high")
        details.append(f"⚠️  Yield {div_yield_pct:.1f}% (possible dividend trap)")
    elif div_yield_pct > 0:
        details.append(f"❌ Yield {div_yield_pct:.1f}% (below 3% minimum)")
    else:
        details.append("❌ Yield: N/A or zero")

    # 2. Payout Ratio (2 pts)
    if payout_ratio is not None:
        pct = payout_ratio * 100
        if 40 <= pct <= 70:
            score += 2
            details.append(f"✅ Payout Ratio {pct:.0f}% (healthy 40–70%)")
        elif 70 < pct <= 90:
            score += 1
            details.append(f"🟡 Payout Ratio {pct:.0f}% (elevated, watch sustainability)")
        elif pct > 90:
            flags.append(f"⚠️  UNSUSTAINABLE PAYOUT — {pct:.0f}% > 90%, leaves little for reinvestment")
            details.append(f"❌ Payout Ratio {pct:.0f}% (dangerously high, dividend at risk)")
        elif 20 <= pct < 40:
            score += 1
            details.append(f"🟡 Payout Ratio {pct:.0f}% (conservative, room to grow dividend)")
        else:
            details.append(f"❌ Payout Ratio {pct:.0f}% (very low, dividendcommitment unclear)")
    else:
        details.append("⚪ Payout Ratio: N/A")

    # 3. Operating Cash Flow (2 pts)
    if operating_cf is not None:
        if operating_cf > 0:
            score += 2
            details.append(f"✅ Operating Cash Flow: positive (Rp {operating_cf:,.0f})")
        else:
            flags.append("⚠️  NEGATIVE CASH FLOW — dividend may be funded by debt, not operations")
            details.append(f"❌ Operating Cash Flow: negative (Rp {operating_cf:,.0f})")
    else:
        details.append("⚪ Operating Cash Flow: N/A")

    # 4. Debt-to-Equity (2 pts)
    if der is not None:
        if is_bank:
            # Banks structurally carry high leverage; relaxed threshold
            if der <= 800:
                score += 2
                details.append(f"✅ DER {der:.0f}% (acceptable for banking sector)")
            elif der <= 1500:
                score += 1
                details.append(f"🟡 DER {der:.0f}% (elevated, even for banks)")
            else:
                details.append(f"❌ DER {der:.0f}% (very high even for banking)")
        else:
            if der <= 50:
                score += 2
                details.append(f"✅ DER {der:.0f}% (low debt, strong balance sheet)")
            elif der <= 150:
                score += 1
                details.append(f"🟡 DER {der:.0f}% (moderate debt)")
            else:
                details.append(f"❌ DER {der:.0f}% (high debt, financial risk)")
    else:
        details.append("⚪ Debt-to-Equity: N/A")

    # 5. Positive EPS (1 pt)
    if eps is not None:
        if eps > 0:
            score += 1
            details.append(f"✅ EPS: Rp {eps:,.0f} (profitable)")
        else:
            flags.append("⚠️  LOSS-MAKING — EPS is negative; dividend sustainability is at risk")
            details.append(f"❌ EPS: Rp {eps:,.0f} (company is losing money)")
    else:
        details.append("⚪ EPS: N/A")

    # 6. Dividend Consistency via 5yr Avg Yield (1 pt)
    if five_yr_yield is not None and five_yr_yield > 0:
        score += 1
        details.append(f"✅ 5yr Avg Yield: {five_yr_yield:.1f}% (consistent dividend payer)")
    else:
        details.append("⚪ 5yr Avg Yield: N/A (consistency unverified)")

    return score, max_score, details, flags


def get_quality_badge(score, max_score):
    """Return a letter-grade badge from quality score."""
    ratio = score / max_score if max_score > 0 else 0
    if ratio >= 0.80:
        return "🏆 A"
    elif ratio >= 0.60:
        return "✅ B"
    elif ratio >= 0.40:
        return "🟡 C"
    else:
        return "❌ D"


# ============================================================
# Analysis helpers (pure functions – no I/O)
# ============================================================
def compute_portfolio_metrics(stock_info, lots, avg_price):
    """Compute P/L, yield-on-cost, and recommendation for a single holding.

    Returns a dict with all computed metrics.
    """
    current = stock_info["current_price"]
    total_shares = lots * SHARES_PER_LOT
    invested = total_shares * avg_price
    market_value = total_shares * current

    unrealized_pl = market_value - invested
    pl_pct = ((current - avg_price) / avg_price * 100) if avg_price > 0 else 0.0

    # Yield-on-cost = annual dividend / avg buy price
    dividend_rate = stock_info.get("dividend_rate") or 0
    yield_on_cost = (dividend_rate / avg_price * 100) if avg_price > 0 else 0.0

    target = stock_info.get("target_price", 0)
    low52  = stock_info.get("fifty_two_week_low", 0)
    high52 = stock_info.get("fifty_two_week_high", 0)

    recommendation = _determine_recommendation(current, avg_price, target, low52, high52)

    target_alloc  = get_target_allocation(stock_info["symbol"])
    gap           = max(0, target_alloc - invested)
    lots_to_target = int(gap / (current * SHARES_PER_LOT)) if current > 0 else 0

    return {
        "total_shares":     total_shares,
        "invested":         invested,
        "market_value":     market_value,
        "unrealized_pl":    unrealized_pl,
        "pl_pct":           pl_pct,
        "yield_on_cost":    yield_on_cost,
        "recommendation":   recommendation,
        "lots_to_target":   lots_to_target,
        "target_allocation": target_alloc,
    }


def _determine_recommendation(current, avg_price, target, low52, high52):
    """Determine HOLD / AVG DOWN recommendation for dividend investors.

    Logic (dividend-focused — never sell, optimize for income):
    - STRONG AVG DOWN : price near 52w low AND below avg_price (max discount, boost yield-on-cost)
    - AVG DOWN        : price < avg_price by ≥ 5% (cheaper than cost, lower your avg)
    - STRONG HOLD     : price ≥ avg_price by ≥ 20% (great yield-on-cost, keep collecting)
    - DON'T ADD MORE  : price near 52w high (too expensive to avg up, wait for dip)
    - HOLD            : everything else (steady, keep collecting dividends)
    """
    if avg_price <= 0 or current <= 0:
        return "⚪ INSUFFICIENT DATA"

    price_vs_avg_pct = (current - avg_price) / avg_price * 100

    # At or below 52-week low AND below avg price → best time to avg down
    if low52 > 0 and current <= low52 * 1.05 and price_vs_avg_pct < -3:
        return "🟢 STRONG AVG DOWN (near 52w low, {:.1f}% below avg)".format(price_vs_avg_pct)

    # Moderately below avg price → avg down opportunity
    if price_vs_avg_pct <= -5:
        return "🟢 AVG DOWN ({:.1f}% below avg price)".format(price_vs_avg_pct)

    # Below target and below avg → mild avg down
    if target > 0 and current < target and price_vs_avg_pct < -2:
        return "🟢 AVG DOWN (below target & {:.1f}% below avg)".format(price_vs_avg_pct)

    # Near 52-week high → don't add more at this price, wait for dip
    if high52 > 0 and current >= high52 * 0.95 and price_vs_avg_pct >= 15:
        return "🟡 DON'T ADD MORE (near 52w high, wait for dip to add)"

    # Big gain → great yield-on-cost, strong hold & keep collecting
    if price_vs_avg_pct >= 20:
        return "💎 STRONG HOLD (+{:.1f}% gain, excellent yield-on-cost!)".format(price_vs_avg_pct)

    # Holding zone – steady
    return "🔵 HOLD (P/L: {:+.1f}%)".format(price_vs_avg_pct)


def get_investment_grade(current, target, low52, div_yield, quality_score=None, quality_max=10):
    """Grade a stock's attractiveness as a dividend investment.

    Combines yield, valuation, and (optionally) quality score.
    """
    # Normalise yield: yfinance returns 0.085 for 8.5%
    dy = (div_yield or 0)
    dy_pct = dy * 100 if dy < 1 else dy

    if dy_pct < 3.0:
        return "Not Recommended (Yield < 3%)"
    if current <= 0:
        return "Insufficient Data"

    # Dividend trap guard
    if dy_pct > 15.0:
        return "⚠️  DIVIDEND TRAP RISK (yield suspiciously high)"

    discount  = ((target - current) / target * 100) if target > 0 else 0
    near_low  = (current <= low52 * 1.10) if low52 > 0 else False
    quality_ok = (quality_score is None) or (quality_score / quality_max >= 0.50)

    if dy_pct >= 8.0 and (discount > 10 or near_low) and quality_ok:
        return "⭐ HIGHLY RECOMMENDED (Great yield + Discounted + Quality)"
    elif dy_pct >= 8.0 and (discount > 10 or near_low):
        return "✅ RECOMMENDED (Great yield + Discounted)"
    elif dy_pct >= 5.0 and discount >= 0 and quality_ok:
        return "✅ RECOMMENDED (Good yield + Fair price + Quality)"
    elif dy_pct >= 5.0 and discount >= 0:
        return "🟡 FAIR (Good yield, but review quality indicators)"
    elif discount < -10:
        return "❌ NOT RECOMMENDED (Overvalued)"
    else:
        return "🟡 FAIR (Wait for a dip)"


def filter_high_yield(stocks, threshold):
    """Return stocks with dividend yield above threshold, sorted descending."""
    def _pct(y):
        return y * 100 if y < 1 else y

    result = [s for s in stocks if s["yield"] is not None and _pct(s["yield"]) > threshold]
    return sorted(result, key=lambda x: _pct(x["yield"]), reverse=True)


# ============================================================
# Notification
# ============================================================
def send_mac_notification(title, text):
    """Send a native macOS notification."""
    script = f'display notification "{text}" with title "{title}" sound name "Glass"'
    subprocess.run(["osascript", "-e", script])


# ============================================================
# Display helpers
# ============================================================
def _fmt_yield(raw_yield):
    """Normalise and format a yfinance yield value as '8.50%'."""
    if raw_yield is None:
        return "N/A"
    pct = raw_yield * 100 if raw_yield < 1 else raw_yield
    return f"{pct:.2f}%"


def _fmt_date(unix_ts):
    """Convert a Unix timestamp from yfinance into a human-readable date string.

    Returns 'DD MMM YYYY' (e.g. '15 Apr 2025') or 'N/A' if None/zero.
    """
    if not unix_ts:
        return "N/A"
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%d %b %Y")
    except Exception:
        return "N/A"


def print_watchlist_summary(high_yield_stocks):
    """Print watchlist scan results with entry recommendations and quality score."""
    print("\n" + "=" * 65)
    print("  WATCHLIST — High Dividend Yield Stocks (>{:.0f}%)".format(THRESHOLD))
    print("=" * 65)

    for stock in high_yield_stocks:
        current = stock.get("current_price", 0)
        target  = stock.get("target_price", 0)
        low52   = stock.get("fifty_two_week_low", 0)

        if target > 0 and current < target:
            entry_rec = f"Good entry (price BELOW target Rp {target:,.0f})"
        elif target > 0 and current >= target:
            entry_rec = f"Wait for dip to Rp {target:,.0f} or 52w Low Rp {low52:,.0f}"
        elif low52 > 0:
            entry_rec = f"Wait for dip near 52w Low Rp {low52:,.0f}"
        else:
            entry_rec = f"Insufficient data. Current: Rp {current:,.0f}"

        score, max_s, details, flags = compute_quality_score(stock)
        badge = get_quality_badge(score, max_s)
        grade = get_investment_grade(current, target, low52, stock["yield"], score, max_s)

        print(f"\n[{stock['symbol']}] {stock['name']}")
        print(f"  Yield:          {_fmt_yield(stock['yield'])}")
        print(f"  Current:        Rp {current:,.0f}"   if current > 0 else "  Current:        N/A")
        print(f"  Target:         Rp {target:,.0f}"    if target > 0  else "  Target:         N/A")
        print(f"  52w Low:        Rp {low52:,.0f}"     if low52 > 0   else "  52w Low:        N/A")
        print(f"  Ex-Div Date:    {_fmt_date(stock.get('ex_dividend_date'))}")
        print(f"  Last Paid:      {_fmt_date(stock.get('last_dividend_date'))}")
        print(f"  Entry Rec:      {entry_rec}")
        print(f"  Grade:          {grade}")
        print(f"  Quality Score:  {score}/{max_s}  {badge}")

        if flags:
            for f in flags:
                print(f"  {f}")

        # Print per-criterion breakdown
        print(f"  {'─' * 55}")
        for d in details:
            print(f"    {d}")


def print_portfolio_analysis(portfolio_results):
    """Print portfolio analysis with hold/avg-down recommendations and quality score."""
    print("\n" + "=" * 65)
    print("  MY PORTFOLIO — Hold / Avg Down Analysis")
    print("=" * 65)

    total_invested = 0
    total_market   = 0

    for item in portfolio_results:
        info       = item["info"]
        metrics    = item["metrics"]
        lots       = item["lots"]
        avg_price  = item["avg_price"]

        total_invested += metrics["invested"]
        total_market   += metrics["market_value"]

        pl_sign       = "+" if metrics["unrealized_pl"] >= 0 else ""
        div_yield_str = _fmt_yield(info["yield"])

        score, max_s, details, flags = compute_quality_score(info)
        badge = get_quality_badge(score, max_s)

        print(f"\n{'─' * 60}")
        print(f"  [{info['symbol']}] {info['name']}")
        print(f"  {'─' * 55}")
        print(f"  Lots:              {lots} ({metrics['total_shares']:,} shares)")
        print(f"  Avg Buy Price:     Rp {avg_price:,.0f}")
        print(f"  Current Price:     Rp {info['current_price']:,.0f}")
        print(f"  52w Range:         Rp {info['fifty_two_week_low']:,.0f} — Rp {info['fifty_two_week_high']:,.0f}")
        if info.get("target_price", 0) > 0:
            print(f"  Target Price:      Rp {info['target_price']:,.0f}")
        else:
            print(f"  Target Price:      N/A")
        print(f"  Invested:          Rp {metrics['invested']:,.0f}")
        print(f"  Market Value:      Rp {metrics['market_value']:,.0f}")
        print(f"  Unrealized P/L:    {pl_sign}Rp {metrics['unrealized_pl']:,.0f} ({pl_sign}{metrics['pl_pct']:.2f}%)")
        print(f"  Div Yield:         {div_yield_str}")
        print(f"  Yield on Cost:     {metrics['yield_on_cost']:.2f}%")
        print(f"  Ex-Div Date:       {_fmt_date(info.get('ex_dividend_date'))}")
        print(f"  Last Paid:         {_fmt_date(info.get('last_dividend_date'))}")

        # Quality indicators
        payout = info.get("payout_ratio")
        der    = info.get("debt_to_equity")
        ocf    = info.get("operating_cashflow")
        eps    = info.get("trailing_eps")
        print(f"  Payout Ratio:      {f'{payout*100:.0f}%' if payout is not None else 'N/A'}")
        print(f"  Debt/Equity:       {f'{der:.0f}%' if der is not None else 'N/A'}")
        print(f"  Oper. Cash Flow:   {f'Rp {ocf:,.0f}' if ocf is not None else 'N/A'}")
        print(f"  EPS:               {f'Rp {eps:,.0f}' if eps is not None else 'N/A'}")
        print(f"  Quality Score:     {score}/{max_s}  {badge}")

        if flags:
            for f in flags:
                print(f"  {f}")

        print(f"  ➤ Recommendation:  {metrics['recommendation']}")
        if metrics["lots_to_target"] > 0:
            print(f"  ➤ Target Lots:     Buy {metrics['lots_to_target']} more lots to reach Rp {metrics['target_allocation']:,.0f}")
        else:
            print(f"  ➤ Target Lots:     Target allocation of Rp {metrics['target_allocation']:,.0f} reached.")

    # Grand totals
    total_pl     = total_market - total_invested
    total_pl_pct = (total_pl / total_invested * 100) if total_invested > 0 else 0
    pl_sign      = "+" if total_pl >= 0 else ""

    print(f"\n{'=' * 60}")
    print(f"  PORTFOLIO TOTALS")
    print(f"  {'─' * 55}")
    print(f"  Total Invested:    Rp {total_invested:,.0f}")
    print(f"  Total Mkt Value:   Rp {total_market:,.0f}")
    print(f"  Total P/L:         {pl_sign}Rp {total_pl:,.0f} ({pl_sign}{total_pl_pct:.2f}%)")
    print(f"{'=' * 60}\n")


def print_new_recommendations(high_yield_stocks, portfolio_tickers):
    """Recommend new high-yield stocks not yet in portfolio."""
    print("\n" + "=" * 65)
    print("  NEW ADDITION RECOMMENDATIONS (Not in Portfolio)")
    print("=" * 65)

    portfolio_symbols = {t.replace(".JK", "") for t in portfolio_tickers}
    candidates = [s for s in high_yield_stocks if s["symbol"] not in portfolio_symbols]

    recommended = []
    for s in candidates:
        score, max_s, _, _ = compute_quality_score(s)
        grade = get_investment_grade(s["current_price"], s["target_price"], s["fifty_two_week_low"], s["yield"], score, max_s)
        if "RECOMMENDED" in grade and "NOT" not in grade:
            recommended.append((s, grade, score, max_s))

    # Sort: quality score (grade) first, then dividend yield
    recommended.sort(key=lambda x: (-x[2], -((x[0].get("yield") or 0) * 100 if (x[0].get("yield") or 0) < 1 else (x[0].get("yield") or 0))))

    if not recommended:
        print("  No new strong candidates found today based on target price, yield, and quality.")
        return []

    for stock, grade, score, max_s in recommended:
        badge = get_quality_badge(score, max_s)
        print(f"\n[{stock['symbol']}] {stock['name']}")
        print(f"  Yield:          {_fmt_yield(stock['yield'])}")
        print(f"  Current:        Rp {stock['current_price']:,.0f}")
        print(f"  Grade:          {grade}")
        print(f"  Quality Score:  {score}/{max_s}  {badge}")
        target_alloc = get_target_allocation(stock["symbol"])
        current_price = stock["current_price"]
        recommended_lots = int(target_alloc / (current_price * SHARES_PER_LOT)) if current_price > 0 else 0
        print(f"  Action:         Consider buying {recommended_lots} lots to reach target Rp {target_alloc:,.0f}")

    return recommended


def print_overall_strategy(portfolio_results, new_candidates):
    """Determine whether to prioritize averaging down vs. buying new stocks.

    Buckets:
    - STRONG BUY  : price at discount AND quality score >= 5/10
    - CAUTION     : price at discount BUT quality score < 5/10 (possible trap)
    - HOLD        : at target allocation or not at a discount
    """
    QUALITY_THRESHOLD = 5  # minimum score out of 10 to be a "safe" avg-down

    print("\n" + "=" * 65)
    print("  OVERALL PORTFOLIO STRATEGY — WHAT TO DO NEXT")
    print("=" * 65)

    strong_buys = []   # discount + quality ✅
    caution_list = []  # discount but poor quality ⚠️

    for p in portfolio_results:
        metrics = p["metrics"]
        info    = p["info"]
        score, max_s, _, flags = compute_quality_score(info)
        badge = get_quality_badge(score, max_s)
        grade = get_investment_grade(
            info["current_price"], info["target_price"],
            info["fifty_two_week_low"], info["yield"], score, max_s
        )

        is_at_discount = (
            "AVG DOWN" in metrics["recommendation"]
            or "RECOMMENDED" in grade
        )

        if metrics["lots_to_target"] > 0 and is_at_discount:
            entry = {
                "symbol":  info["symbol"],
                "rec":     metrics["recommendation"],
                "grade":   grade,
                "lots":    metrics["lots_to_target"],
                "score":   score,
                "max_s":   max_s,
                "badge":   badge,
                "flags":   flags,
            }
            if score >= QUALITY_THRESHOLD:
                strong_buys.append(entry)
            else:
                caution_list.append(entry)

    # ── Step 1: Avg down existing holdings ────────────────────
    print(f"\n  STEP 1 — AVG DOWN YOUR EXISTING HOLDINGS")
    print(f"  {'─' * 60}")
    if strong_buys:
        print("  Below target allocation, at a discount, AND financially")
        print("  sound. Fill these gaps BEFORE deploying into new stocks.\n")
        for e in strong_buys:
            clean_rec = e["rec"].split("(")[0].strip() if "(" in e["rec"] else e["rec"]
            print(f"   ✅ [{e['symbol']}] Buy up to {e['lots']} lots")
            print(f"       Rec:     {clean_rec}")
            print(f"       Grade:   {e['grade']}")
            print(f"       Quality: {e['score']}/{e['max_s']}  {e['badge']}")
            if e["flags"]:
                for f in e["flags"]:
                    print(f"       {f}")
            print()
    else:
        print("  None today — all holdings are either at target allocation,")
        print("  not at a discount, or quality score is too low to add more.\n")

    # ── Step 2: New stocks with remaining capital ──────────────
    print(f"  STEP 2 — DEPLOY REMAINING CAPITAL INTO NEW STOCKS")
    print(f"  {'─' * 60}")
    if new_candidates:
        if strong_buys:
            print("  After filling the gaps above, deploy remaining capital")
            print("  into these quality new additions:\n")
        else:
            print("  No avg-down needed — go straight to new additions:\n")
        for stock, grade, score, max_s in new_candidates:
            badge = get_quality_badge(score, max_s)
            print(f"   ✅ [{stock['symbol']}] {stock['name']}")
            print(f"       Yield:   {_fmt_yield(stock['yield'])}")
            print(f"       Grade:   {grade}")
            print(f"       Quality: {score}/{max_s}  {badge}")
            target_alloc = get_target_allocation(stock["symbol"])
            current_price = stock["current_price"]
            recommended_lots = int(target_alloc / (current_price * SHARES_PER_LOT)) if current_price > 0 else 0
            print(f"       Action:  Buy ~{recommended_lots} lots (Target: Rp {target_alloc:,.0f})")
            print()
    else:
        print("  No strong new candidates today.")
        print("  Build cash reserves and wait for better entry points.\n")

    # ── Caution bucket (always shown last if present) ──────────
    if caution_list:
        print(f"  ⚠️  CAUTION — Price looks cheap but quality score is LOW (<5/10):")
        print("  Do NOT average down until the fundamentals improve.\n")
        for e in caution_list:
            print(f"   ⚠️  [{e['symbol']}] {e['lots']} lots | Quality: {e['score']}/{e['max_s']}  {e['badge']}")
            if e["flags"]:
                for f in e["flags"]:
                    print(f"        {f}")
        print()

    print()


def print_dividend_calendar(portfolio_results, all_stock_data, high_yield_stocks):
    """Show monthly dividend PAYMENT coverage and suggest gap-filler stocks.

    Goal: collect at least one dividend payment every month of the year.

    Note: yfinance only provides historical ex-dividend dates for IDX stocks.
    Payment months are approximated by shifting ex-dates forward by
    PAYMENT_OFFSET_DAYS (~30 days), which reflects the typical IDX payment lag.
    Adjust PAYMENT_OFFSET_DAYS at the top of the file if needed.
    """
    print("\n" + "=" * 65)
    print("  DIVIDEND INCOME CALENDAR  (by estimated payment month)")
    print(f"  ► Goal: receive dividend cash every month of the year")
    print(f"  ► Approximation: ex-date + {PAYMENT_OFFSET_DAYS} days (typical IDX payment lag)")
    print("=" * 65)

    portfolio_symbols = {p["info"]["symbol"] for p in portfolio_results}
    watchlist_symbols = {s["symbol"] for s in high_yield_stocks}

    # Build month → [symbols] map from portfolio holdings
    month_coverage = {m: [] for m in range(1, 13)}
    for p in portfolio_results:
        info = p["info"]
        for m in info.get("payment_months", set()):
            month_coverage[m].append(info["symbol"])

    # Print calendar row by row
    print()
    uncovered = []
    for m in range(1, 13):
        name  = MONTH_NAMES[m - 1]
        payers = month_coverage[m]
        if payers:
            print(f"  {name}  ✅  {', '.join(sorted(payers))}")
        else:
            print(f"  {name}  ❌  (no coverage)")
            uncovered.append(m)

    # Summary
    covered = 12 - len(uncovered)
    print(f"\n  Coverage: {covered}/12 months")

    if not uncovered:
        print("  🎉 Your portfolio already covers all 12 months!")
        return

    uncovered_names = [MONTH_NAMES[m - 1] for m in uncovered]
    print(f"  Missing:  {', '.join(uncovered_names)}")

    # Find gap fillers from watchlist + watchlist universe that cover uncovered months
    print(f"\n  {'─' * 60}")
    print("  SUGGESTED STOCKS TO FILL THE GAPS")
    print("  (stocks historically paying in your missing months)")
    print(f"  {'─' * 60}")

    # Collect all non-portfolio stocks and their payment months
    candidates = {}   # symbol → set of months
    sym_to_info = {}  # symbol → info dict
    for ticker_symbol, info in all_stock_data.items():
        sym = info["symbol"]
        if sym in portfolio_symbols:
            continue
        months = info.get("payment_months", set())
        if months:
            candidates[sym] = months
            sym_to_info[sym] = info

    any_found = False
    for m in uncovered:
        month_name = MONTH_NAMES[m - 1]
        fillers = [
            sym for sym, months in candidates.items()
            if m in months
        ]
        if fillers:
            any_found = True
            
            # Sort: grade (quality score) first, then dividend yield, then watchlist, then alphabetical
            def sort_key(s):
                info = sym_to_info[s]
                score, _, _, _ = compute_quality_score(info)
                dy = info.get("yield") or 0
                return (-score, -dy, 0 if s in watchlist_symbols else 1, s)

            fillers.sort(key=sort_key)
            
            tagged = []
            for s in fillers[:6]:  # cap at 6 per month for readability
                info = sym_to_info[s]
                score, max_s, _, _ = compute_quality_score(info)
                badge_letter = get_quality_badge(score, max_s).split()[-1]
                dy = info.get("yield") or 0
                dy_pct = f"{dy*100:.1f}%" if dy < 1 else f"{dy:.1f}%"
                marker = " ⭐" if s in watchlist_symbols else ""
                tagged.append(f"{s} ({badge_letter}, {dy_pct}){marker}")

            print(f"\n  {month_name}: {', '.join(tagged)}")
        else:
            print(f"\n  {month_name}: No candidates found in current watchlist")

    if any_found:
        print("\n  ⭐ = also in high-yield watchlist (prioritise these)")
    print()


# ============================================================
# Main
# ============================================================
def main():
    # --- Step 1: Fetch data for all unique tickers (watchlist + portfolio) ---
    all_tickers = set(TICKERS) | set(MY_PORTFOLIO.keys())
    print(f"Fetching data for {len(all_tickers)} tickers...")

    stock_data = {}
    for ticker_symbol in sorted(all_tickers):
        info = fetch_stock_info(ticker_symbol)
        if info:
            stock_data[ticker_symbol] = info
            status = _fmt_yield(info["yield"]) if info["yield"] else "no yield"
            print(f"  ✓ {ticker_symbol}: {status}")
        else:
            print(f"  ✗ {ticker_symbol}: fetch failed")

    # --- Step 2: Watchlist scan (high-yield alert) ---
    watchlist_infos = [stock_data[t] for t in TICKERS if t in stock_data]
    high_yield = filter_high_yield(watchlist_infos, THRESHOLD)

    if high_yield:
        # macOS notification (top 5)
        msg = ""
        for s in high_yield[:5]:
            msg += f"{s['symbol']}: {_fmt_yield(s['yield'])}\\n"
        if len(high_yield) > 5:
            msg += f"...and {len(high_yield) - 5} more."
        send_mac_notification("High Dividend Alert (IDX)", msg)
        print_watchlist_summary(high_yield)
    else:
        print(f"\nNo watchlist stocks above {THRESHOLD}% yield today.")

    # --- Step 3: Portfolio analysis (hold / avg down) ---
    portfolio_results = []
    for ticker_symbol, holding in MY_PORTFOLIO.items():
        if ticker_symbol not in stock_data:
            print(f"\n⚠ {ticker_symbol}: no market data, skipping portfolio analysis")
            continue

        info    = stock_data[ticker_symbol]
        metrics = compute_portfolio_metrics(info, holding["lots"], holding["avg_price"])
        portfolio_results.append({
            "info":      info,
            "metrics":   metrics,
            "lots":      holding["lots"],
            "avg_price": holding["avg_price"],
        })

    # Sort ascending by P/L% so worst performers appear first
    portfolio_results.sort(key=lambda x: x["metrics"]["pl_pct"])

    if portfolio_results:
        print_portfolio_analysis(portfolio_results)
    else:
        print("\nNo portfolio data to analyze.")

    # --- Step 4: Dividend income calendar ---
    print_dividend_calendar(portfolio_results, stock_data, high_yield)

    # --- Step 5: Recommend new additions ---
    new_candidates = print_new_recommendations(high_yield, MY_PORTFOLIO.keys())

    # --- Step 6: Overall strategy ---
    print_overall_strategy(portfolio_results, new_candidates)


if __name__ == "__main__":
    main()
