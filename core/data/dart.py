"""
금융감독원 DART 공시 수집기
https://opendart.fss.or.kr/
"""
import os
import requests
from typing import Optional
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY", "")
DART_BASE_URL = "https://opendart.fss.or.kr/api"


def fetch_recent_disclosures(
    corp_code: Optional[str] = None,
    bgn_de: Optional[str] = None,
    end_de: Optional[str] = None,
    pblntf_ty: str = "A",  # A=정기공시, B=주요사항, C=발행공시, D=지분공시
    page_no: int = 1,
    page_count: int = 20,
) -> list[dict]:
    """DART 공시 목록 조회

    Args:
        corp_code: 고유번호 (None이면 전체)
        bgn_de: 시작일 "YYYYMMDD"
        end_de: 종료일 "YYYYMMDD"
        pblntf_ty: 공시 유형
        page_no: 페이지 번호
        page_count: 페이지당 건수 (max 100)

    Returns:
        공시 목록 리스트
    """
    if not DART_API_KEY:
        logger.error("DART_API_KEY not set in .env")
        return []

    params = {
        "crtfc_key": DART_API_KEY,
        "pblntf_ty": pblntf_ty,
        "page_no": page_no,
        "page_count": page_count,
    }

    if corp_code:
        params["corp_code"] = corp_code
    if bgn_de:
        params["bgn_de"] = bgn_de
    if end_de:
        params["end_de"] = end_de

    try:
        resp = requests.get(f"{DART_BASE_URL}/list.json", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "000":
            logger.warning(f"DART API error: {data.get('message')}")
            return []

        items = data.get("list", [])
        logger.info(f"Fetched {len(items)} disclosures from DART")
        return items

    except Exception as e:
        logger.error(f"DART fetch failed: {e}")
        return []


def fetch_disclosure_text(rcept_no: str) -> str:
    """공시 원문 텍스트 조회 (감성 분석용)

    Args:
        rcept_no: 접수번호 (공시 목록에서 획득)

    Returns:
        공시 텍스트
    """
    if not DART_API_KEY:
        return ""

    params = {
        "crtfc_key": DART_API_KEY,
        "rcept_no": rcept_no,
    }

    try:
        resp = requests.get(f"{DART_BASE_URL}/document.json", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("report", "")
    except Exception as e:
        logger.error(f"Failed to fetch disclosure {rcept_no}: {e}")
        return ""


if __name__ == "__main__":
    disclosures = fetch_recent_disclosures(page_count=5)
    for d in disclosures[:3]:
        print(f"[{d.get('rcept_dt')}] {d.get('corp_name')} — {d.get('report_nm')}")
