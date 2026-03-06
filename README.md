# 📈 inv — Personal Quant Platform

개인 퀀트 투자 플랫폼. AI 기반 뉴스 감성 분석 + 자동매매 + 백테스팅 엔진.

## 구조

```
inv/
├── core/           # Python 핵심 엔진 (데이터, 감성분석, 백테스팅)
├── api/            # FastAPI 서버
├── agents/         # Claude 서브에이전트
├── scripts/        # 실행 스크립트
├── web/            # Next.js 대시보드 (Phase 3)
└── infra/          # Docker, CI/CD
```

## 시작하기

```bash
cp .env.example .env
# .env 파일에 API 키 입력

cd core
pip install -r requirements.txt

python scripts/run_signal.py
```

## Phase 계획
- **Phase 1** (1~2개월): 데이터 파이프라인 + 감성 분석 에이전트
- **Phase 2** (2~3개월): 자동매매 + FastAPI 서버
- **Phase 3** (3~4개월): Next.js 대시보드 + 구독 플랫폼
- **Phase 4** (4개월~): 전략 마켓플레이스 런칭
