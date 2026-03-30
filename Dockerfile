FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim

ARG GENAI_TOOLBOX_VERSION=0.31.0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN curl -fsSL "https://storage.googleapis.com/genai-toolbox/v${GENAI_TOOLBOX_VERSION}/linux/amd64/toolbox" \
    -o /usr/local/bin/toolbox \
    && chmod +x /usr/local/bin/toolbox

COPY agent ./agent
COPY backend ./backend
COPY mcp_server ./mcp_server
COPY start_mcp.py ./start_mcp.py
COPY setup_bq.py ./setup_bq.py
COPY README.md ./README.md
COPY .env.example ./.env.example
COPY start_cloud_run.sh ./start_cloud_run.sh
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN chmod +x /app/start_cloud_run.sh

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV MCP_TOOLBOX_PORT=5000

EXPOSE 8080

CMD ["/app/start_cloud_run.sh"]
