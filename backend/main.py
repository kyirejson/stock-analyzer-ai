import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
from supabase import create_client, Client

app = FastAPI(title="Stock Analyzer API")

# CORS - allow all origins for simplicity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Environment Variables ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyAM4hDHpcfwTqhO4vlAjfn1mxkUbKGFqsE")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# Initialize Supabase (optional - only if env vars are set)
supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- Models ---
class AnalyzeRequest(BaseModel):
    ticker: str


# --- Helper: Fetch Stock Data ---
def get_stock_data(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        hist = stock.history(period="5d")

        if hist.empty:
            raise ValueError(f"No data found for ticker: {ticker}")

        prices = hist["Close"].tolist()
        dates = [str(d.date()) for d in hist.index]

        return {
            "ticker": ticker.upper(),
            "name": info.get("longName", ticker.upper()),
            "current_price": round(prices[-1], 2) if prices else None,
            "previous_close": round(info.get("previousClose", 0), 2),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "volume": info.get("volume"),
            "avg_volume": info.get("averageVolume"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "price_history": {"dates": dates, "prices": [round(p, 2) for p in prices]},
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch stock data: {str(e)}")


# --- Helper: Call Gemini API ---
def analyze_with_gemini(stock_data: dict) -> dict:
    prompt = f"""You are a professional stock analyst. Analyze the following stock data and return ONLY a valid JSON object with no markdown, no code blocks, no extra text.

Stock Data:
- Ticker: {stock_data['ticker']}
- Company: {stock_data['name']}
- Current Price: ${stock_data['current_price']}
- Previous Close: ${stock_data['previous_close']}
- Market Cap: {stock_data['market_cap']}
- P/E Ratio: {stock_data['pe_ratio']}
- 52-Week High: {stock_data['52_week_high']}
- 52-Week Low: {stock_data['52_week_low']}
- Sector: {stock_data['sector']}
- Industry: {stock_data['industry']}
- Recent 5-Day Prices: {stock_data['price_history']['prices']}

Return EXACTLY this JSON structure (no other text):
{{
  "summary": "A concise 2-3 sentence analysis of this stock's current situation and outlook",
  "sentiment": "Bullish",
  "risk_level": "Medium",
  "key_points": ["point 1", "point 2", "point 3"],
  "recommendation": "Brief action recommendation"
}}

Rules:
- sentiment MUST be exactly one of: "Bullish", "Neutral", "Bearish"
- risk_level MUST be exactly one of: "Low", "Medium", "High"
- Return ONLY the JSON object, nothing else
"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json"
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        GEMINI_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            # Parse the JSON response
            analysis = json.loads(text)

            # Validate required fields
            required = ["summary", "sentiment", "risk_level", "key_points", "recommendation"]
            for field in required:
                if field not in analysis:
                    raise ValueError(f"Missing field: {field}")

            # Validate enum values
            if analysis["sentiment"] not in ["Bullish", "Neutral", "Bearish"]:
                analysis["sentiment"] = "Neutral"
            if analysis["risk_level"] not in ["Low", "Medium", "High"]:
                analysis["risk_level"] = "Medium"

            return analysis

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise HTTPException(status_code=502, detail=f"Gemini API error: {body}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from Gemini: {str(e)}")


# --- Helper: Save to Supabase ---
def save_to_supabase(stock_data: dict, analysis: dict):
    if not supabase:
        return {"saved": False, "reason": "Supabase not configured"}

    try:
        record = {
            "ticker": stock_data["ticker"],
            "company_name": stock_data["name"],
            "current_price": stock_data["current_price"],
            "summary": analysis["summary"],
            "sentiment": analysis["sentiment"],
            "risk_level": analysis["risk_level"],
            "key_points": analysis["key_points"],
            "recommendation": analysis["recommendation"],
            "raw_stock_data": stock_data,
            "created_at": datetime.utcnow().isoformat(),
        }
        result = supabase.table("stock_analyses").insert(record).execute()
        return {"saved": True, "id": result.data[0]["id"] if result.data else None}
    except Exception as e:
        return {"saved": False, "reason": str(e)}


# --- Routes ---
@app.get("/")
def root():
    return {"message": "Stock Analyzer API is running", "version": "1.0"}


@app.get("/health")
def health():
    return {"status": "ok", "supabase_connected": supabase is not None}


@app.get("/stock/{ticker}")
def get_stock(ticker: str):
    """Fetch stock market data for a given ticker symbol."""
    return get_stock_data(ticker)


@app.post("/analyze")
def analyze_stock(req: AnalyzeRequest):
    """Fetch stock data + AI analysis + save to Supabase."""
    # 1. Get stock data
    stock_data = get_stock_data(req.ticker)

    # 2. AI analysis
    analysis = analyze_with_gemini(stock_data)

    # 3. Save to Supabase
    save_result = save_to_supabase(stock_data, analysis)

    return {
        "stock": stock_data,
        "analysis": analysis,
        "storage": save_result
    }


@app.get("/history")
def get_history(limit: int = 10):
    """Get recent analyses from Supabase."""
    if not supabase:
        return {"data": [], "message": "Supabase not configured"}

    try:
        result = supabase.table("stock_analyses") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return {"data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
