FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/* && useradd --system --uid 10001 --create-home editor
RUN mkdir /data && chown 10001:10001 /data
WORKDIR /app
COPY --chown=10001:10001 *.py ./
COPY --chown=10001:10001 web ./web
USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 C4PCUT_CONTAINER=1
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz',timeout=3).read()"
CMD ["python","server.py"]
