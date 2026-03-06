"""
Claude API 기반 뉴스/공시 감성 분석기
뉴스 텍스트 → 매수/매도/중립 신호 + 신뢰도 스코어
"""
import os
import json
from typing import Optional
import anthropic
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """당신은 주식 시장 전문 감성 분석 AI입니다.
주어진 뉴스나 공시 텍스트를 분석하여 특정 종목 또는 시장 전반에 대한 투자 신호를 생성합니다.

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요:
{
  "signal": "BUY" | "SELL" | "NEUTRAL",
  "score": -1.0 ~ 1.0,  // -1=강한매도, 0=중립, 1=강한매수
  "confidence": 0.0 ~ 1.0,  // 분석 신뢰도
  "reasoning": "판단 근거 (1~2문장)",
  "key_factors": ["핵심 요인1", "핵심 요인2"],
  "risk_level": "LOW" | "MEDIUM" | "HIGH"
}

score 가이드:
- 0.7 ~ 1.0: 강한 매수 신호 (실적 호조, 대형 수주, 긍정적 정책)
- 0.3 ~ 0.7: 약한 매수 신호
- -0.3 ~ 0.3: 중립
- -0.7 ~ -0.3: 약한 매도 신호
- -1.0 ~ -0.7: 강한 매도 신호 (실적 악화, 소송, 부정적 이슈)"""


def analyze_sentiment(
    text: str,
    ticker: Optional[str] = None,
    context: Optional[str] = None,
) -> dict:
    """뉴스/공시 텍스트 감성 분석

    Args:
        text: 분석할 뉴스/공시 텍스트
        ticker: 관련 종목 (선택, 예: "005930", "AAPL")
        context: 추가 컨텍스트 (예: 현재 시장 상황)

    Returns:
        {signal, score, confidence, reasoning, key_factors, risk_level}
    """
    if not text.strip():
        return _neutral_result("Empty text")

    user_content = f"분석할 텍스트:\n{text[:2000]}"  # 2000자 제한

    if ticker:
        user_content = f"종목: {ticker}\n\n{user_content}"
    if context:
        user_content += f"\n\n시장 컨텍스트: {context}"

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        raw = message.content[0].text.strip()

        # JSON 파싱
        result = json.loads(raw)
        result["raw_text_preview"] = text[:100]
        logger.info(f"Sentiment [{ticker or 'market'}]: {result['signal']} (score={result['score']:.2f})")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e} — raw: {raw[:200]}")
        return _neutral_result("Parse error")
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        return _neutral_result(str(e))


def analyze_batch(articles: list[dict], ticker: Optional[str] = None) -> list[dict]:
    """뉴스 리스트 일괄 감성 분석

    Args:
        articles: fetch_rss_news() 또는 fetch_all_news() 결과
        ticker: 관련 종목

    Returns:
        각 기사에 sentiment 필드 추가된 리스트
    """
    results = []
    for article in articles:
        text = f"{article.get('title', '')}\n{article.get('summary', '')}"
        sentiment = analyze_sentiment(text, ticker=ticker)
        results.append({**article, "sentiment": sentiment})

    # 평균 스코어 계산
    scores = [r["sentiment"]["score"] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    logger.info(f"Batch analysis complete: {len(results)} articles, avg_score={avg_score:.2f}")

    return results


def get_aggregate_signal(analyzed_articles: list[dict]) -> dict:
    """분석된 기사들의 종합 투자 신호 생성

    Args:
        analyzed_articles: analyze_batch() 결과

    Returns:
        {signal, avg_score, article_count, buy_count, sell_count, neutral_count}
    """
    if not analyzed_articles:
        return _neutral_result("No articles")

    scores = [a["sentiment"]["score"] for a in analyzed_articles]
    signals = [a["sentiment"]["signal"] for a in analyzed_articles]

    avg_score = sum(scores) / len(scores)
    buy_count = signals.count("BUY")
    sell_count = signals.count("SELL")
    neutral_count = signals.count("NEUTRAL")

    if avg_score >= 0.3:
        signal = "BUY"
    elif avg_score <= -0.3:
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    return {
        "signal": signal,
        "avg_score": round(avg_score, 3),
        "article_count": len(analyzed_articles),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "neutral_count": neutral_count,
    }


def _neutral_result(reason: str = "") -> dict:
    return {
        "signal": "NEUTRAL",
        "score": 0.0,
        "confidence": 0.0,
        "reasoning": reason,
        "key_factors": [],
        "risk_level": "MEDIUM",
    }


if __name__ == "__main__":
    # 테스트
    test_news = """
    삼성전자가 3분기 영업이익이 전년 동기 대비 274% 증가한 9조1000억원을 기록했다고 발표했다.
    반도체 부문의 HBM 수요 급증과 파운드리 수주 확대가 실적 개선을 이끌었다.
    """

    result = analyze_sentiment(test_news, ticker="005930")
    print(json.dumps(result, ensure_ascii=False, indent=2))
