# 📡 StockRadar India v3.0
### Full-Featured Nifty 500 Live Research Platform — 100% Free

---

## ✅ What's Fixed in v3.0

- **All Nifty 500 stocks** — 500 real NSE symbols, no duplicates
- **Live prices** from Yahoo Finance (yfinance) via your backend — no fake/random data
- **Backend ↔ Frontend properly connected** — enter your Render URL once, auto-saves
- **AI via Groq (Free)** — Llama 3 70B model, no API key required from users
  - Falls back to rule-based analysis when GROQ key not set
- **No consumer API key needed** — AI runs on backend
- **Fixed yfinance API** — updated for latest yfinance 0.2.x compatibility
- **Batch quote loading** — loads prices progressively (25 → 100 → 200 → 500)
- **Auto-refresh every 60 seconds**

---

## 🚀 Deploy in 15 Minutes (Free)

### Step 1: Deploy Backend on Render.com (Free)

1. Fork or upload this code to GitHub
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Settings:
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `gunicorn app:app --workers 2 --timeout 120`
   - **Plan:** Free
5. (Optional) Add env var `GROQ_API_KEY` for free AI features

### Step 2: Get Free Groq API Key (for AI)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up for free
3. Create API key
4. In Render dashboard → Environment → Add `GROQ_API_KEY = <your-key>`
5. Redeploy — AI features activate automatically!

### Step 3: Use the Frontend

1. Open `index.html` in any browser (just double-click, no server needed!)
2. Enter your Render URL: `https://your-app.onrender.com`
3. Click **CONNECT**
4. Done! Live data loads automatically

---

## 🔌 API Endpoints

| Endpoint | Description | Cache |
|----------|-------------|-------|
| `GET /api/stocks` | Full Nifty 500 list | Static |
| `GET /api/quote/<SYM>` | Live quote for 1 stock | 60s |
| `GET /api/quotes/batch?symbols=TCS,INFY,...` | Batch quotes (max 25) | 60s |
| `GET /api/fundamentals/<SYM>` | P/E, ROE, margins etc | 5min |
| `GET /api/history/<SYM>?period=1y&interval=1d` | OHLCV history | 5min |
| `GET /api/financials/<SYM>` | Quarterly/Annual P&L | 1hr |
| `GET /api/news/<SYM>` | Stock-specific news | 10min |
| `GET /api/indices` | Nifty/Sensex/BankNifty | 60s |
| `GET /api/market-news` | Market news | 10min |
| `POST /api/ai/analyze` | AI stock analysis | Live |
| `POST /api/ai/chat` | AI market chat | Live |
| `GET /api/health` | Health check | - |

---

## 📊 Features

### 📈 Live Stock Table
- All 500 Nifty 500 stocks with live prices
- Sortable columns (Market Cap, % Change, P/E, Volume)
- Search by symbol or company name
- Filter by sector
- Live price flash on update (green/red)
- Mini 52W range bar
- Quick TA signal per stock

### 🔥 Market Heatmap
- Color-coded by % change (green = up, red = down)
- Size by Market Cap / Volume / Equal
- Filter by sector
- Click any cell to open stock detail

### 🌐 Market Overview
- Sector performance rankings
- Top 8 gainers / losers
- Most active by volume
- Near 52W high / near 52W low

### 📋 Stock Detail Panel
- Full price stats (open, high, low, prev close, volume, market cap)
- Interactive price chart (5D/1M/3M/6M/1Y/2Y/5Y)
- 22+ fundamental metrics with color-coded analysis
- 9-indicator Technical Analysis panel (RSI, MACD, Bollinger, Stochastic, MAs)
- Overall BUY/SELL/HOLD signal
- Quarterly revenue + net profit bar charts
- Annual financial statements
- Latest news for the stock

### 🤖 AI Research Report
- Click "🤖 AI Analyze" on any stock
- Generates institutional-quality research report via Llama 3 on Groq
- Verdict: STRONG BUY / BUY / HOLD / SELL / STRONG SELL
- Bull case, Bear case, Valuation, Target price
- Falls back to rule-based analysis if no AI key

### 💬 AI Market Chat
- Chat with AI about Indian markets
- Context-aware with live market data
- Powered by Llama 3 70B on Groq (free)
- Pre-built quick-question buttons

### 🔍 Stock Screener
- Filter by P/E, ROE, Market Cap, Dividend Yield, P/B, Net Margin, Sector
- Runs on all loaded stocks
- Results in sortable table

### 💼 Portfolio Tracker
- Add holdings with quantity, avg price, buy date
- Real-time P&L calculation
- Day change tracking
- Allocation pie chart
- Persists in localStorage

---

## 🛠 Tech Stack

| Component | Technology | Cost |
|-----------|-----------|------|
| Frontend | Pure HTML/CSS/JS | Free |
| Backend | Python/Flask | Free |
| Data | Yahoo Finance (yfinance) | Free |
| AI | Groq API (Llama 3 70B) | Free* |
| Hosting | Render.com | Free** |
| Charts | Chart.js | Free |

*Free tier: 14,400 requests/day on Groq
**Free tier: spins down after 15min inactivity, 750 hrs/month

---

## ⚠️ Important Notes

1. **Yahoo Finance data** is delayed ~15 minutes during market hours on free tier
2. **Render free tier** spins down — first request after inactivity takes 30-60s to wake up
3. **Rate limiting** — backend caches data aggressively to avoid Yahoo Finance blocks
4. **Fundamentals** load on-demand per stock (5 min cache)
5. **Not SEBI-registered** — for educational/research purposes only

---

## 🔧 Local Development

```bash
pip install flask flask-cors yfinance requests gunicorn
python app.py
# Backend runs at http://localhost:5000

# Open index.html in browser
# Set backend URL to http://localhost:5000
```
