ARG UV_IMAGE
FROM ${UV_IMAGE}
WORKDIR /workspace/services/backend
COPY services/backend/ ./
RUN uv sync --frozen
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
