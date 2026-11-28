FROM python:3.13-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY request_logging.py ./

FROM base AS products
COPY main.py shop_catalog.py workout_exercises.json ./
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS orders
COPY orders_uebung.py ./
CMD ["python", "-m", "uvicorn", "orders_uebung:app", "--host", "0.0.0.0", "--port", "8000"]
