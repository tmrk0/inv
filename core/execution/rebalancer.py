"""
ETF 듀얼 모멘텀 리밸런서

흐름:
  1. yfinance로 최근 가격 수집 → 모멘텀 신호 계산 → 목표 포트폴리오 결정
  2. KIS 잔고 조회 → 현재 포지션 파악
  3. 목표 vs 현재 비교 → 매도/매수 주문 목록 산출
  4. 매도 먼저 실행 → 매수 실행 (dry_run=True면 출력만)

Usage:
    from core.execution.kis import KISClient
    from core.execution.rebalancer import ETFRebalancer

    client = KISClient()
    rb = ETFRebalancer(client)
    rb.run(dry_run=True)   # 시뮬레이션
    rb.run(dry_run=False)  # 실제 주문
"""
import math
import yfinance as yf
import pandas as pd
from loguru import logger

from core.execution.kis import KISClient, EXCHANGE_MAP, DEFAULT_EXCHANGE
from core.strategies.etf_rotation import (
    DEFAULT_UNIVERSE,
    CASH_TICKER,
    _momentum_scores,
)

# 현재가 조회 기간 (모멘텀 계산용 충분한 데이터)
PRICE_PERIOD = "2y"


def _fetch_prices(tickers: list[str]) -> pd.DataFrame:
    raw = yf.download(tickers, period=PRICE_PERIOD, progress=False, auto_adjust=True)
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]] if "Close" in raw.columns else raw
    if isinstance(prices, pd.Series):
        prices = prices.to_frame(tickers[0])
    return prices.dropna(how="all")


def _spot_prices(tickers: list[str]) -> dict[str, float]:
    """yfinance로 현재가(최근 종가) 조회 → {ticker: price}"""
    raw = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
    else:
        close = raw[["Close"]] if "Close" in raw.columns else raw
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    last = close.ffill().iloc[-1]
    return {t: float(last[t]) for t in tickers if t in last.index}


class ETFRebalancer:
    """ETF 듀얼 모멘텀 리밸런서

    Args:
        kis:       KISClient 인스턴스
        tickers:   투자 유니버스 (기본: DEFAULT_UNIVERSE)
        top_n:     매월 보유할 최대 ETF 수
        lookback:  모멘텀 계산 기간 (거래일)
        skip:      최근 제외 기간 (거래일, 룩어헤드 방지)
        rf_annual: 연 무위험 이자율 (절대 모멘텀 기준)
        use_absolute_momentum: True면 음수 모멘텀 시 현금(BIL) 전환
    """

    def __init__(
        self,
        kis: KISClient = None,
        tickers: list[str] = None,
        top_n: int = 2,
        lookback: int = 126,
        skip: int = 21,
        rf_annual: float = 0.035,
        use_absolute_momentum: bool = True,
    ):
        self.kis      = kis
        self.tickers  = list(tickers or DEFAULT_UNIVERSE)
        self.top_n    = top_n
        self.lookback = lookback
        self.skip     = skip
        self.rf_annual = rf_annual
        self.use_absolute_momentum = use_absolute_momentum

        if CASH_TICKER not in self.tickers:
            self.tickers.append(CASH_TICKER)

    # ── 신호 계산 ──────────────────────────────────────────────────────────────

    def get_signal(self) -> dict:
        """현재 시점 모멘텀 신호 → 목표 포트폴리오

        Returns:
            {
              "target":   ["SPY", "QQQ"],   # 보유할 ETF 목록
              "momentum": {"SPY": 0.12, ...},
              "in_cash":  False,            # True면 절대 모멘텀 필터로 현금 전환
            }
        """
        logger.info("모멘텀 신호 계산 중...")
        prices = _fetch_prices(self.tickers)

        if len(prices) < self.lookback + self.skip + 1:
            raise RuntimeError(
                f"데이터 부족: {len(prices)}일 (필요: {self.lookback + self.skip + 1}일)"
            )

        mom = _momentum_scores(prices, self.lookback, self.skip).dropna()
        rf_period = (1 + self.rf_annual) ** (self.lookback / 252) - 1

        investable = mom.drop(labels=[CASH_TICKER], errors="ignore")

        if self.use_absolute_momentum:
            investable = investable[investable > rf_period]

        in_cash = len(investable) == 0
        if in_cash:
            target = [CASH_TICKER]
        else:
            target = list(
                investable.sort_values(ascending=False).head(self.top_n).index
            )

        mom_dict = {t: round(float(mom.get(t, 0)), 4) for t in self.tickers if t in mom}
        logger.info(
            f"목표 포트폴리오: {target} "
            f"| {'현금 전환' if in_cash else '모멘텀 상위'}"
        )
        return {"target": target, "momentum": mom_dict, "in_cash": in_cash}

    # ── 주문 산출 ──────────────────────────────────────────────────────────────

    def compute_orders(
        self,
        target: list[str],
        positions: list[dict],
        cash_usd: float,
        prices: dict[str, float],
    ) -> dict:
        """목표 포트폴리오 달성을 위한 매도/매수 주문 목록 산출

        Args:
            target:    목표 ETF 목록
            positions: KIS 잔고 output1 ({"ticker", "qty", "avg_price", ...})
            cash_usd:  현재 USD 예수금
            prices:    현재가 {ticker: price}

        Returns:
            {
              "sells": [{"ticker", "qty", "exchange"}],
              "buys":  [{"ticker", "qty", "exchange", "estimated_price"}],
              "portfolio_value_usd": float,
            }
        """
        current = {p["ticker"]: p for p in positions}
        target_set = set(t.upper() for t in target)

        # 현재 포트폴리오 총 가치 계산
        holdings_value = sum(
            p["qty"] * prices.get(p["ticker"], p["avg_price"])
            for p in positions
        )
        portfolio_value = cash_usd + holdings_value
        logger.info(f"포트폴리오 총 가치: ${portfolio_value:,.2f} (현금: ${cash_usd:,.2f})")

        sells = []
        for ticker, pos in current.items():
            if ticker not in target_set:
                excd = EXCHANGE_MAP.get(ticker, DEFAULT_EXCHANGE)
                sells.append({
                    "ticker":   ticker,
                    "qty":      int(pos["qty"]),
                    "exchange": excd,
                })
                logger.info(f"  매도 예정: {ticker} {int(pos['qty'])}주")

        # 매도 후 예상 현금
        sell_proceeds = sum(
            s["qty"] * prices.get(s["ticker"], 0) for s in sells
        )
        available_cash = cash_usd + sell_proceeds

        buys = []
        alloc_per_etf = available_cash / len(target) if target else 0
        for ticker in target:
            ticker = ticker.upper()
            price  = prices.get(ticker, 0)
            if price <= 0:
                logger.warning(f"  {ticker} 현재가 없음 — 매수 스킵")
                continue
            qty = math.floor(alloc_per_etf / price)
            if qty <= 0:
                logger.warning(f"  {ticker} 매수 가능 수량 0 (가격: ${price:.2f}, 배분: ${alloc_per_etf:.2f})")
                continue
            excd = EXCHANGE_MAP.get(ticker, DEFAULT_EXCHANGE)
            buys.append({
                "ticker":           ticker,
                "qty":              qty,
                "exchange":         excd,
                "estimated_price":  price,
            })
            logger.info(f"  매수 예정: {ticker} {qty}주 @ ${price:.2f} ≈ ${qty * price:,.2f}")

        return {
            "sells":                sells,
            "buys":                 buys,
            "portfolio_value_usd":  round(portfolio_value, 2),
        }

    # ── 실행 ───────────────────────────────────────────────────────────────────

    def run(self, dry_run: bool = True) -> dict:
        """리밸런싱 실행

        Args:
            dry_run: True면 주문 목록만 출력, False면 실제 KIS 주문

        Returns:
            {"signal", "orders", "executed_sells", "executed_buys"}
        """
        mode = "[DRY RUN]" if dry_run else "[LIVE]"
        logger.info(f"=== ETF 리밸런서 {mode} 시작 ===")

        # 1. 신호 계산
        signal = self.get_signal()
        target = signal["target"]

        # 2. KIS 잔고 조회
        balance  = self.kis.get_balance()
        positions = balance["positions"]
        cash_usd  = balance["cash_usd"]

        # 현재 포지션이 이미 목표와 동일하면 스킵
        current_tickers = {p["ticker"] for p in positions}
        if current_tickers == set(t.upper() for t in target) and current_tickers:
            logger.info("포트폴리오 변경 없음 — 리밸런싱 스킵")
            return {"signal": signal, "orders": None, "skipped": True}

        # 3. 현재가 조회 (yfinance)
        all_tickers = list({p["ticker"] for p in positions} | set(target))
        prices = _spot_prices(all_tickers)

        # 4. 주문 산출
        orders = self.compute_orders(target, positions, cash_usd, prices)

        if dry_run:
            logger.info(f"[DRY RUN] 매도: {len(orders['sells'])}건, 매수: {len(orders['buys'])}건")
            return {"signal": signal, "orders": orders, "executed_sells": [], "executed_buys": []}

        # 5. 매도 먼저
        executed_sells = []
        for s in orders["sells"]:
            try:
                result = self.kis.order(s["ticker"], "sell", s["qty"], s["exchange"])
                executed_sells.append(result)
            except Exception as e:
                logger.error(f"매도 실패 {s['ticker']}: {e}")

        # 6. 매수
        executed_buys = []
        for b in orders["buys"]:
            try:
                result = self.kis.order(
                    b["ticker"], "buy", b["qty"], b["exchange"], price=b["estimated_price"]
                )
                executed_buys.append(result)
            except Exception as e:
                logger.error(f"매수 실패 {b['ticker']}: {e}")

        logger.info(
            f"=== 리밸런싱 완료 | 매도: {len(executed_sells)}건, 매수: {len(executed_buys)}건 ==="
        )
        return {
            "signal":          signal,
            "orders":          orders,
            "executed_sells":  executed_sells,
            "executed_buys":   executed_buys,
        }
