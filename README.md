# Beginner Friendly Finance App
Most AI finance tools try to tell you what to do with your money. This project takes a different approach. It uses AI to make complicated financial information understandable, while leaving the analysis and decisions to the user. The goal isn't to replace financial judgment. It's to help people develop it.

A beginner-friendly financial education web app (Flask + vanilla JS). Specs live in `docs/`.

## Setup (Windows PowerShell)

```powershell
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env   # then add your API keys
```

The app starts without `.env` or keys, in demo mode.

## Run

```powershell
venv\Scripts\python app.py      # http://localhost:5000
```

## Tests

```powershell
venv\Scripts\python -m pytest
```

## Scripts

```powershell
venv\Scripts\python scripts\check_endpoints.py   # checks provider endpoints, writes data/endpoint_check.json
venv\Scripts\python scripts\build_demo_data.py   # rebuilds data/demo_stocks.json from yfinance
```

## Optional: Sentiment Explorer (local FinBERT)

Off by default. It classifies fixed, fictional example statements with the Hugging Face model
`ProsusAI/finbert`, run locally on the CPU. The core app and tests do not need it.

```powershell
venv\Scripts\python -m pip install -r requirements-sentiment.txt   # about 155 MB download
venv\Scripts\python scripts\download_sentiment_model.py            # about 438 MB, once, to the Hugging Face cache
$env:SENTIMENT_ENABLED="1"; venv\Scripts\python app.py
```

FinBERT weights are licensed CC BY-NC-SA 4.0 (non-commercial use only). They are stored in the
Hugging Face cache outside this repository and must never be committed. If the packages or weights
are missing, the explorer reports "Model unavailable" and shows no sentiment.
