FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --extra postgres
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home app && mkdir -p /app/data && chown -R app:app /app
USER app
EXPOSE 8000
CMD [".venv/bin/outthere", "serve", "--host", "0.0.0.0"]
