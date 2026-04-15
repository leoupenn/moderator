# Browser game (Express + Socket.IO + static web). Skips the PySide6 desktop app.
FROM node:22-bookworm-slim

WORKDIR /app

COPY web/package.json web/package-lock.json ./web/
COPY server/package.json server/package-lock.json ./server/

RUN cd web && npm ci
RUN cd server && npm ci

COPY web ./web
COPY server ./server

RUN cd server && npm run build

ENV NODE_ENV=production
WORKDIR /app/server
CMD ["node", "dist/index.js"]
