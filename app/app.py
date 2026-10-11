import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import gradio as gr
import pandas as pd
import plotly.graph_objects as go
import plotly.subplots as sp
import yfinance as yf

# ---------------------------------------------------------------------------
# Stock universes
# ---------------------------------------------------------------------------
POPULAR_50 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
    "JNJ", "WMT", "PG", "MA", "HD", "DIS", "BAC", "XOM", "COST", "ABBV",
    "KO", "PFE", "AVGO", "TMO", "MRK", "LLY", "CVX", "CSCO", "ACN", "MCD",
    "NEE", "DHR", "AMD", "INTC", "QCOM", "TXN", "INTU", "AMGN", "UNH", "RTX",
    "CAT", "BA", "GS", "AXP", "SPGI", "BLK", "MMM", "IBM", "GE", "F",
]

NASDAQ_100 = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA", "AVGO", "COST", "ASML",
    "NFLX", "AMD", "ADBE", "QCOM", "INTC", "INTU", "CSCO", "TXN", "AMGN", "AMAT",
    "MU", "LRCX", "KLAC", "MRVL", "PANW", "ADI", "REGN", "GILD", "MDLZ", "VRTX",
    "BKNG", "ADP", "ISRG", "PYPL", "MELI", "CDNS", "SNPS", "FTNT", "WDAY", "CTAS",
    "MNST", "PCAR", "ORLY", "ROST", "CPRT", "DXCM", "IDXX", "CHTR", "KDP", "EXC",
]

SECTORS = [
    "All", "Technology", "Healthcare", "Financial Services", "Consumer Cyclical",
    "Communication Services", "Industrials", "Consumer Defensive", "Energy",
    "Basic Materials", "Real Estate", "Utilities",
]

SORT_COLUMNS = [
    "Mkt Cap ($B)", "Change %", "P/E", "Fwd P/E", "P/B",
    "Div Yield %", "Volume (M)", "Rev Growth %", "ROE %", "Beta", "Price",
]

# ---------------------------------------------------------------------------
# Simple in-memory cache
# ---------------------------------------------------------------------------
_cache: dict = {}
_cache_ts: dict = {}
_cache_lock = threading.Lock()
CACHE_TTL = 300  # seconds


def _cache_get(key):
    with _cache_lock:
        if key in _cache and time.time() - _cache_ts.get(key, 0) < CACHE_TTL:
            return _cache[key]
    return None


def _cache_set(key, value):
    with _cache_lock:
        _cache[key] = value
        _cache_ts[key] = time.time()


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def get_sp500_tickers() -> list[str]:
    cached = _cache_get("sp500")
    if cached:
        return cached
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        tickers = tables[0]["Symbol"].tolist()
        _cache_set("sp500", tickers)
        return tickers
    except Exception:
        return POPULAR_50


def fetch_stock_info(ticker: str) -> dict | None:
    key = f"info_{ticker}"
    cached = _cache_get(key)
    if cached:
        return cached

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose")

        change_pct = None
        if price and prev and prev > 0:
            change_pct = (price - prev) / prev * 100

        mkt_cap = info.get("marketCap")

        def safe(val, mult=1, digits=2):
            return round(val * mult, digits) if val is not None else None

        result = {
            "Ticker":         ticker,
            "Company":        info.get("shortName", ticker),
            "Sector":         info.get("sector", "N/A"),
            "Industry":       info.get("industry", "N/A"),
            "Price":          safe(price),
            "Change %":       safe(change_pct),
            "Mkt Cap ($B)":   safe(mkt_cap, 1 / 1e9),
            "P/E":            safe(info.get("trailingPE")),
            "Fwd P/E":        safe(info.get("forwardPE")),
            "P/B":            safe(info.get("priceToBook")),
            "Div Yield %":    safe(info.get("trailingAnnualDividendYield"), 100) or 0.0,
            "Beta":           safe(info.get("beta")),
            "Volume (M)":     safe(info.get("volume"), 1 / 1e6),
            "52W High":       safe(info.get("fiftyTwoWeekHigh")),
            "52W Low":        safe(info.get("fiftyTwoWeekLow")),
            "Rev Growth %":   safe(info.get("revenueGrowth"), 100),
            "Profit Margin %": safe(info.get("profitMargins"), 100),
            "ROE %":          safe(info.get("returnOnEquity"), 100),
            "Debt/Equity":    safe(info.get("debtToEquity")),
        }
        _cache_set(key, result)
        return result
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------
def apply_range(df: pd.DataFrame, col: str, lo, hi) -> pd.DataFrame:
    if col not in df.columns:
        return df
    if lo is not None:
        df = df[df[col].notna() & (df[col] >= lo)]
    if hi is not None:
        df = df[df[col].notna() & (df[col] <= hi)]
    return df


# ---------------------------------------------------------------------------
# Screener logic
# ---------------------------------------------------------------------------
def screen_stocks(
    universe, custom_tickers, sector_filter,
    min_price, max_price, min_mktcap, max_mktcap,
    min_pe, max_pe, min_div, max_div,
    min_change, max_change,
    sort_by, sort_asc,
    progress=gr.Progress(),
):
    # Resolve ticker list
    if universe == "Custom":
        tickers = [t.strip().upper() for t in custom_tickers.split(",") if t.strip()]
        if not tickers:
            return pd.DataFrame(), "Enter at least one ticker symbol."
    elif universe == "S&P 500":
        progress(0, desc="Fetching S&P 500 list...")
        tickers = get_sp500_tickers()
    elif universe == "Nasdaq 100":
        tickers = NASDAQ_100
    else:
        tickers = POPULAR_50

    total = len(tickers)
    done = [0]
    results = []

    def fetch(t):
        data = fetch_stock_info(t)
        done[0] += 1
        progress(done[0] / total, desc=f"Fetching {done[0]}/{total}...")
        return data

    with ThreadPoolExecutor(max_workers=15) as ex:
        for future in as_completed({ex.submit(fetch, t): t for t in tickers}):
            r = future.result()
            if r:
                results.append(r)

    if not results:
        return pd.DataFrame(), "No data returned. Check your tickers or network connection."

    df = pd.DataFrame(results)

    # Sector filter
    if sector_filter != "All":
        df = df[df["Sector"] == sector_filter]

    # Range filters
    df = apply_range(df, "Price",        min_price,  max_price)
    df = apply_range(df, "Mkt Cap ($B)", min_mktcap, max_mktcap)
    df = apply_range(df, "P/E",          min_pe,     max_pe)
    df = apply_range(df, "Div Yield %",  min_div,    max_div)
    df = apply_range(df, "Change %",     min_change, max_change)

    # Sort
    if sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=sort_asc, na_position="last")

    df = df.reset_index(drop=True)
    summary = f"Found **{len(df)}** stocks (screened {total})"
    return df, summary


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------
def get_stock_chart(ticker: str, period: str):
    if not ticker or not ticker.strip():
        return None, ""
    ticker = ticker.strip().upper()
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return None, f"No data for **{ticker}**."

        info = stock.info
        company = info.get("shortName", ticker)
        price = info.get("currentPrice") or hist["Close"].iloc[-1]
        prev = info.get("previousClose") or (hist["Close"].iloc[-2] if len(hist) > 1 else price)
        chg = (price - prev) / prev * 100 if prev else 0
        chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
        chg_color = "green" if chg >= 0 else "red"

        fig = sp.make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.03, row_heights=[0.75, 0.25],
        )
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist["Open"], high=hist["High"],
            low=hist["Low"], close=hist["Close"],
            name="Price",
        ), row=1, col=1)
        bar_colors = [
            "rgba(0,180,0,0.7)" if c >= o else "rgba(220,0,0,0.7)"
            for c, o in zip(hist["Close"], hist["Open"])
        ]
        fig.add_trace(go.Bar(
            x=hist.index, y=hist["Volume"],
            name="Volume", marker_color=bar_colors,
        ), row=2, col=1)

        fig.update_layout(
            title=(
                f"{company} ({ticker})  "
                f"${price:.2f}  "
                f"<span style='color:{chg_color}'>{chg_str}</span>"
            ),
            yaxis_title="Price (USD)",
            yaxis2_title="Volume",
            height=620,
            template="plotly_white",
            showlegend=False,
            xaxis_rangeslider_visible=False,
            margin=dict(t=60, b=20, l=60, r=20),
        )

        mkt_cap = info.get("marketCap")
        pe = info.get("trailingPE")
        div = info.get("trailingAnnualDividendYield")
        beta = info.get("beta")
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "")

        lines = [
            f"### {company} ({ticker})",
            f"**Sector:** {sector}" + (f" — {industry}" if industry else ""),
            f"**Price:** ${price:.2f} ({chg_str})",
        ]
        if mkt_cap:
            lines.append(f"**Market Cap:** ${mkt_cap/1e9:.2f}B")
        if pe:
            lines.append(f"**P/E Ratio:** {pe:.2f}")
        if div:
            lines.append(f"**Dividend Yield:** {div*100:.2f}%")
        if beta:
            lines.append(f"**Beta:** {beta:.2f}")

        return fig, "  \n".join(lines)
    except Exception as e:
        return None, f"Error loading **{ticker}**: {e}"


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------
with gr.Blocks(title="Stock Screener") as demo:
    gr.Markdown("# Stock Screener")
    gr.Markdown("Real-time stock data via Yahoo Finance. Results are cached for 5 minutes.")

    with gr.Tabs():
        # ── Screener ────────────────────────────────────────────────────────
        with gr.TabItem("Screener"):
            with gr.Row():
                with gr.Column(scale=1, min_width=260):
                    gr.Markdown("#### Universe")
                    universe = gr.Radio(
                        choices=["Popular 50", "Nasdaq 100", "S&P 500", "Custom"],
                        value="Popular 50", label="",
                    )
                    custom_tickers_box = gr.Textbox(
                        label="Tickers (comma-separated)",
                        placeholder="AAPL, MSFT, TSLA...",
                        visible=False,
                    )

                    gr.Markdown("#### Filters")
                    sector_dd = gr.Dropdown(choices=SECTORS, value="All", label="Sector")

                    with gr.Row():
                        min_price  = gr.Number(label="Min Price ($)",    value=None)
                        max_price  = gr.Number(label="Max Price ($)",    value=None)
                    with gr.Row():
                        min_mktcap = gr.Number(label="Min Mkt Cap ($B)", value=None)
                        max_mktcap = gr.Number(label="Max Mkt Cap ($B)", value=None)
                    with gr.Row():
                        min_pe     = gr.Number(label="Min P/E",          value=None)
                        max_pe     = gr.Number(label="Max P/E",          value=None)
                    with gr.Row():
                        min_div    = gr.Number(label="Min Div Yield %",  value=None)
                        max_div    = gr.Number(label="Max Div Yield %",  value=None)
                    with gr.Row():
                        min_change = gr.Number(label="Min Day Chg %",    value=None)
                        max_change = gr.Number(label="Max Day Chg %",    value=None)

                    gr.Markdown("#### Sort")
                    sort_by  = gr.Dropdown(choices=SORT_COLUMNS, value="Mkt Cap ($B)", label="Sort by")
                    sort_asc = gr.Checkbox(label="Ascending", value=False)

                    run_btn = gr.Button("Run Screen", variant="primary", size="lg")

                with gr.Column(scale=3):
                    status_md  = gr.Markdown("")
                    results_df = gr.DataFrame(interactive=False, wrap=False)

        # ── Chart ───────────────────────────────────────────────────────────
        with gr.TabItem("Chart"):
            with gr.Row():
                chart_ticker = gr.Textbox(label="Ticker", placeholder="AAPL", scale=2)
                chart_period = gr.Dropdown(
                    choices=["1mo", "3mo", "6mo", "1y", "2y", "5y"],
                    value="6mo", label="Period", scale=1,
                )
                chart_btn = gr.Button("Load Chart", variant="primary", scale=1)
            stock_info_md = gr.Markdown("")
            chart_plot    = gr.Plot()

    # ── Events ──────────────────────────────────────────────────────────────
    universe.change(
        lambda x: gr.update(visible=(x == "Custom")),
        inputs=[universe], outputs=[custom_tickers_box],
    )

    run_btn.click(
        screen_stocks,
        inputs=[
            universe, custom_tickers_box, sector_dd,
            min_price, max_price, min_mktcap, max_mktcap,
            min_pe, max_pe, min_div, max_div,
            min_change, max_change,
            sort_by, sort_asc,
        ],
        outputs=[results_df, status_md],
    )

    chart_btn.click(
        get_stock_chart,
        inputs=[chart_ticker, chart_period],
        outputs=[chart_plot, stock_info_md],
    )


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
