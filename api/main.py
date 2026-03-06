"""
FastAPI 서버 — inv 퀀트 플랫폼 API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import sentiment, backtest, signal

app = FastAPI(
    title="inv Quant Platform API",
    description="AI 기반 퀀트 투자 플랫폼 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sentiment.router, prefix="/api/sentiment", tags=["Sentiment"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"])
app.include_router(signal.router, prefix="/api/signal", tags=["Signal"])


@app.get("/")
def root():
    return {"status": "ok", "service": "inv Quant Platform"}


@app.get("/health")
def health():
    return {"status": "healthy"}
