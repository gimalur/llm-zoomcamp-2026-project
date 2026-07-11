FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /srv/app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project

COPY app/ ./app
COPY scripts/ ./scripts

ENV PATH="/srv/app/.venv/bin:${PATH}"

WORKDIR /srv/app/app

EXPOSE 8001

CMD ["chainlit", "run", "main.py", "--host", "0.0.0.0", "--port", "8001"]
