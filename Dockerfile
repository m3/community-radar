FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .
COPY src/ ./src/
COPY config.yaml ./
EXPOSE 5001
CMD ["gunicorn", "--bind=0.0.0.0:5001", "--workers=2", "--threads=4", \
     "--timeout=120", "--access-logfile=-", "src.dashboard.app:app"]