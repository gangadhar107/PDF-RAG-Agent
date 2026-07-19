# ── Frontend (TanStack Start / Vite dev server) ──────────────────────────────
# Build:  docker build -t pdf-rag-frontend ./frontend
# Run:    docker run -p 3000:3000 -e VITE_API_URL=http://localhost:8000 pdf-rag-frontend

FROM node:20-slim

WORKDIR /app

# 1. Install dependencies (cached — only re-runs when package.json changes)
COPY package.json ./
RUN npm install

# 2. Copy source
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--port", "3000", "--host", "0.0.0.0"]
