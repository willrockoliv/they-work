# Frontend 2D do TheyWork (Fase 4).
# A imagem é a mesma para dev (vite --host) e para preview da build.
FROM node:22.23.3-alpine

ENV NODE_ENV=development
WORKDIR /app/frontend

# Camada de dependências isolada: só reinstala quando o manifesto muda.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=40s \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["npm", "run", "dev"]
