FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DASHBOARD_PORT=8004

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dashboard_app ./dashboard_app

EXPOSE ${DASHBOARD_PORT}
CMD ["sh", "-c", "exec uvicorn dashboard_app.main:app --host 0.0.0.0 --port \"${DASHBOARD_PORT}\" --no-access-log"]
