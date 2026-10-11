# Stock Screener

A local stock screener with real-time data from Yahoo Finance. Filter stocks by fundamentals and technicals, and view candlestick charts.

## Features

- **Screener tab** — filter from Popular 50, Nasdaq 100, S&P 500, or custom tickers by:
  - Sector, Price, Market Cap, P/E, Dividend Yield, Day Change %
  - Sort by any column, ascending or descending
- **Chart tab** — candlestick + volume chart for any ticker across 1m–5y periods
- Results cached for 5 minutes to reduce API calls

## Usage

1. Click **Install** in the Pinokio sidebar
2. Click **Start** once installation completes
3. The screener opens automatically in the browser

## API

Gradio exposes a REST API automatically. Example using the screener:

### JavaScript
```javascript
const response = await fetch("http://127.0.0.1:7860/run/predict", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    fn_index: 0,
    data: ["Popular 50", "", "All", null, null, null, null, null, null, null, null, null, null, "Mkt Cap ($B)", false]
  })
})
const result = await response.json()
```

### Python
```python
from gradio_client import Client

client = Client("http://127.0.0.1:7860")
result = client.predict(
    universe="Popular 50",
    custom_tickers="",
    sector_filter="All",
    min_price=None, max_price=None,
    min_mktcap=None, max_mktcap=None,
    min_pe=None, max_pe=None,
    min_div=None, max_div=None,
    min_change=None, max_change=None,
    sort_by="Mkt Cap ($B)",
    sort_asc=False,
    api_name="/screen_stocks"
)
```

### Curl
```bash
curl -X POST http://127.0.0.1:7860/run/predict \
  -H "Content-Type: application/json" \
  -d '{"fn_index":0,"data":["Popular 50","","All",null,null,null,null,null,null,null,null,null,null,"Mkt Cap ($B)",false]}'
```
