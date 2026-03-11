"""
KIS (한국투자증권) OpenAPI 클라이언트
해외주식(미국) 매매 지원 — 모의투자/실거래

API 문서: https://apiportal.koreainvestment.com
모의투자 URL: https://openapivts.koreainvestment.com:29443
실거래  URL: https://openapi.koreainvestment.com:9443
"""
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

MOCK_URL = "https://openapivts.koreainvestment.com:29443"
REAL_URL = "https://openapi.koreainvestment.com:9443"

TOKEN_CACHE_PATH = Path(".kis_token.json")

# 미국 주요 ETF/종목 → KIS 거래소 코드 매핑
# NAS=나스닥, NYS=뉴욕, AMS=아멕스(NYSE Arca 포함)
EXCHANGE_MAP: dict[str, str] = {
    "SPY": "AMS", "IVV": "AMS", "VOO": "AMS", "VTI": "AMS",
    "QQQ": "NAS", "TQQQ": "NAS",
    "GLD": "AMS", "IAU": "AMS",
    "TLT": "NAS", "IEF": "NAS", "BND": "NAS",
    "BIL": "AMS",
    "AAPL": "NAS", "MSFT": "NAS", "NVDA": "NAS",
    "AMZN": "NAS", "GOOGL": "NAS", "META": "NAS",
    "TSLA": "NAS",
}
DEFAULT_EXCHANGE = "NAS"

# 실전 매매 tr_id (거래소 무관하게 동일, 매수/매도 구분)
# 참고: https://apiportal.koreainvestment.com/apiservice/apiservice-overseas-stock-order
_REAL_BUY_TR  = "TTTS0308U"
_REAL_SELL_TR = "TTTS0307U"


class KISClient:
    """KIS OpenAPI 클라이언트 (해외주식 전용)

    Usage:
        client = KISClient()                   # .env에서 자동 로드
        price  = client.get_price("SPY")       # 현재가 조회
        bal    = client.get_balance()          # 잔고 조회
        client.order("SPY", "buy", qty=3)      # 매수
        client.liquidate("SPY")                # 전량 매도
    """

    def __init__(
        self,
        app_key: str = None,
        app_secret: str = None,
        account_no: str = None,
        is_mock: bool = None,
    ):
        self.app_key    = app_key    or os.getenv("KIS_APP_KEY", "")
        self.app_secret = app_secret or os.getenv("KIS_APP_SECRET", "")

        raw = account_no or os.getenv("KIS_ACCOUNT_NO", "")
        digits = raw.replace("-", "")
        self.cano         = digits[:8]
        self.acnt_prdt_cd = digits[8:] or "01"

        if is_mock is None:
            is_mock = os.getenv("KIS_IS_MOCK", "true").lower() == "true"
        self.is_mock  = is_mock
        self.base_url = MOCK_URL if is_mock else REAL_URL

        self._access_token:   str | None      = None
        self._token_expires:  datetime | None = None

        mode = "모의투자" if is_mock else "실거래"
        logger.info(f"KIS 클라이언트 초기화 ({mode}) | 계좌: {self.cano}-{self.acnt_prdt_cd}")

    # ── 인증 ──────────────────────────────────────────────────────────────────

    def _load_token_cache(self) -> bool:
        try:
            if not TOKEN_CACHE_PATH.exists():
                return False
            data = json.loads(TOKEN_CACHE_PATH.read_text())
            expires = datetime.fromisoformat(data["expires"])
            if datetime.now() < expires - timedelta(minutes=10):
                self._access_token  = data["token"]
                self._token_expires = expires
                logger.debug("KIS 토큰 캐시 재사용")
                return True
        except Exception:
            pass
        return False

    def _save_token_cache(self):
        TOKEN_CACHE_PATH.write_text(json.dumps({
            "token":   self._access_token,
            "expires": self._token_expires.isoformat(),
        }))

    def get_token(self) -> str:
        """액세스 토큰 반환 (캐시 우선, 만료 시 재발급)"""
        if (self._access_token and self._token_expires
                and datetime.now() < self._token_expires - timedelta(minutes=10)):
            return self._access_token

        if self._load_token_cache():
            return self._access_token

        url  = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey":     self.app_key,
            "appsecret":  self.app_secret,
        }
        resp = requests.post(url, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        self._access_token  = data["access_token"]
        expires_in          = int(data.get("expires_in", 86400))
        self._token_expires = datetime.now() + timedelta(seconds=expires_in)
        self._save_token_cache()
        logger.info("KIS 액세스 토큰 발급 완료")
        return self._access_token

    def _headers(self, tr_id: str) -> dict:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.get_token()}",
            "appkey":        self.app_key,
            "appsecret":     self.app_secret,
            "tr_id":         tr_id,
            "custtype":      "P",  # P=개인
        }

    # ── 잔고 ──────────────────────────────────────────────────────────────────

    def get_balance(self) -> dict:
        """해외주식 잔고 조회

        Returns:
            {
              "positions": [{"ticker", "qty", "avg_price", "current_value", "exchange"}],
              "cash_usd":  float,   # 외화 예수금 (USD)
              "total_eval_usd": float,
            }
        """
        tr_id = "VTTS3012R" if self.is_mock else "TTTS3012R"
        url   = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-balance"

        resp = requests.get(
            url,
            headers=self._headers(tr_id),
            params={
                "CANO":            self.cano,
                "ACNT_PRDT_CD":    self.acnt_prdt_cd,
                "OVRS_EXCG_CD":    "NASD",  # 전체 해외거래소
                "TR_CRCY_CD":      "USD",
                "CTX_AREA_FK200":  "",
                "CTX_AREA_NK200":  "",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(f"잔고 조회 실패: {data.get('msg1')}")

        positions = []
        for item in data.get("output1", []):
            qty = float(item.get("ovrs_cblc_qty", 0))
            if qty > 0:
                positions.append({
                    "ticker":        item.get("ovrs_pdno", ""),
                    "qty":           qty,
                    "avg_price":     float(item.get("pchs_avg_pric", 0)),
                    "current_value": float(item.get("ovrs_stck_evlu_amt", 0)),
                    "exchange":      item.get("ovrs_excg_cd", ""),
                })

        out2 = data.get("output2", {})
        result = {
            "positions":      positions,
            "cash_usd":       float(out2.get("frcr_dps_amt1",  0)),
            "total_eval_usd": float(out2.get("tot_evlu_pfls_amt", 0)),
        }
        logger.info(
            f"잔고 조회 | 보유종목: {len(positions)}개 "
            f"| 예수금: ${result['cash_usd']:,.0f} "
            f"| 평가합계: ${result['total_eval_usd']:,.0f}"
        )
        return result

    # ── 주문 ──────────────────────────────────────────────────────────────────

    def order(
        self,
        ticker:   str,
        side:     str,    # "buy" | "sell"
        qty:      int,
        exchange: str   = None,
        price:    float = 0,  # 0 = 시장가 근사 (지정가 0원으로 전송)
    ) -> dict:
        """해외주식 주문 (매수/매도)

        KIS 해외주식은 지정가만 지원하나, price=0 전달 시 시장가 근사로 처리됨.
        실제 체결가는 주문 후 체결 내역에서 확인 필요.

        Returns:
            {"order_no", "ticker", "side", "qty", "exchange", "status"}
        """
        if qty <= 0:
            raise ValueError(f"주문 수량 오류: {qty}")

        excd = exchange or EXCHANGE_MAP.get(ticker.upper(), DEFAULT_EXCHANGE)

        if self.is_mock:
            tr_id = "VTTS3013U" if side == "buy" else "VTTS3014U"
        else:
            tr_id = _REAL_BUY_TR if side == "buy" else _REAL_SELL_TR

        url  = f"{self.base_url}/uapi/overseas-stock/v1/trading/order"
        body = {
            "CANO":           self.cano,
            "ACNT_PRDT_CD":   self.acnt_prdt_cd,
            "OVRS_EXCG_CD":   excd,
            "PDNO":           ticker.upper(),
            "ORD_DVSN":       "00",              # 00=지정가
            "ORD_QTY":        str(int(qty)),
            "OVRS_ORD_UNPR":  str(price) if price > 0 else "0",
            "ORD_SVR_DVSN_CD": "0",
        }

        resp = requests.post(url, headers=self._headers(tr_id), json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"주문 실패 [{side.upper()} {ticker} {qty}주]: {data.get('msg1')}"
            )

        out      = data.get("output", {})
        order_no = out.get("odno", "")
        logger.info(
            f"주문 완료 | {side.upper()} {ticker} {qty}주 @ {excd} | 주문번호: {order_no}"
        )
        return {
            "order_no": order_no,
            "ticker":   ticker.upper(),
            "side":     side,
            "qty":      qty,
            "exchange": excd,
            "status":   "submitted",
        }

    def liquidate(self, ticker: str, exchange: str = None) -> dict | None:
        """보유 종목 전량 매도. 미보유 시 None 반환."""
        balance = self.get_balance()
        pos = next(
            (p for p in balance["positions"] if p["ticker"] == ticker.upper()),
            None,
        )
        if not pos or pos["qty"] <= 0:
            logger.info(f"{ticker} 미보유 — 청산 스킵")
            return None
        return self.order(ticker, "sell", int(pos["qty"]), exchange)
