FROM python:3.13-slim

RUN useradd --home-dir /app cfdns
WORKDIR /app
RUN chown cfdns /app

ENTRYPOINT ["cloudflare-dyndns"]

ENV PATH=$PATH:/app/.venv/bin

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock /app/
COPY README.md /app/
COPY cloudflare_dyndns /app/cloudflare_dyndns
RUN uv sync
USER cfdns
