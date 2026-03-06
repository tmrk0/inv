FROM python:3.11-slim

WORKDIR /app

# 의존성 설치
COPY core/requirements.txt core/requirements.txt
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r core/requirements.txt -r api/requirements.txt

# 소스 복사
COPY . .

# FastAPI 실행
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
