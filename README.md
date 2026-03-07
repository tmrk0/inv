# 📈 inv — Personal Quant Platform

미국 주식/ETF 중심 개인 퀀트 투자 플랫폼.
AI 기반 감성 분석 + 모멘텀 전략 + 자동매매 + 백테스팅 엔진.

## 구조

```
inv/
├── core/
│   ├── data/           # 시세·뉴스 수집 (yfinance, RSS)
│   ├── sentiment/      # Claude 감성 분석
│   ├── strategies/
│   │   ├── base.py
│   │   ├── etf_rotation.py      # 멀티자산 ETF 듀얼 모멘텀 (핵심)
│   │   └── examples/            # 단일 종목 전략 (MA, RSI, 모멘텀)
│   └── backtester/     # 백테스팅 엔진 (안전장치 포함)
├── api/                # FastAPI 서버
├── agents/             # Claude 서브에이전트
├── scripts/            # 실행 스크립트
│   ├── run_etf_rotation.py  # ETF 로테이션 백테스트
│   ├── run_backtest.py      # 단일 종목 백테스트
│   └── run_signal.py        # 감성 분석 신호
├── web/                # Next.js 대시보드 (Phase 3)
└── infra/              # Docker, CI/CD
```

## 투자 유니버스 (기본)

| 티커 | 자산 | 역할 |
|------|------|------|
| SPY | 미국 대형주 (S&P 500) | 주식 |
| QQQ | 미국 기술주 (나스닥 100) | 주식 |
| GLD | 금 | 실물자산 |
| TLT | 미국 장기국채 (20년+) | 채권 |
| BIL | 단기국채 | 현금 대용 |

## 시작하기

```bash
cp .env.example .env
# .env에 ANTHROPIC_API_KEY, ALPACA_API_KEY 입력

cd core
pip install -r requirements.txt

# ETF 로테이션 백테스트 (10년)
python scripts/run_etf_rotation.py --period 10y --top-n 2

# 단일 종목 모멘텀 백테스트
python scripts/run_backtest.py --ticker SPY --strategy momentum --period 5y --walkforward

# 감성 분석 신호
python scripts/run_signal.py
```

## 백테스터 안전장치

1. **거래비용·슬리피지** — 편도 수수료 + 슬리피지 반영
2. **룩어헤드 방지** — 신호 1일 shift, 모멘텀 skip 적용
3. **손절** — `stop_loss_pct` 기준 일별 체크
4. **ATR 포지션 사이징** — 변동성 기반 자동 크기 조절
5. **최대 비중 제한** — `max_position_pct` 상한
6. **워크포워드 테스트** — 훈련/검증 구간 순차 분리

## Phase 계획

- **Phase 1** ✅ 데이터 파이프라인 + 감성 분석 + 백테스팅 엔진
- **Phase 2** Alpaca 자동매매 연동 + FastAPI 서버
- **Phase 3** Next.js 대시보드
- **Phase 4** 전략 마켓플레이스
