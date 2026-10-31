FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.production PETVISION_DEBUG=0 PETVISION_DATA_DIR=/data PORT=8000
WORKDIR /app
COPY requirements-app.txt requirements-deploy.txt requirements-inference.txt ./
RUN pip install -r requirements-deploy.txt && pip install -r requirements-inference.txt
RUN groupadd -g 10001 petvision && useradd -u 10001 -g petvision -m petvision \
    && mkdir /data && chown petvision:petvision /data
COPY --chown=petvision:petvision backend ./backend
COPY --chown=petvision:petvision ml/artifacts/curated-v2 ./ml/artifacts/curated-v2
USER petvision
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/',timeout=4)" || exit 1
CMD ["python","backend/serve.py"]
