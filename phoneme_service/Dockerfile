FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service
COPY requirements.txt /service/requirements.txt
RUN python -m pip install --no-cache-dir -r /service/requirements.txt
COPY main.py /service/main.py
RUN useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 8080
# Health route does not download model on startup. First inference warms it.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
