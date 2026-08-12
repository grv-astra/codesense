FROM node:20-slim AS build
WORKDIR /app
COPY client/package.json client/package-lock.json ./
RUN npm ci
COPY client/ .
# Same-origin by default: nginx serves the frontend and proxies /api to the
# backend, so requests can be relative ("") instead of an absolute host:port
# -- avoids CORS entirely. Override at build time if serving cross-origin.
ARG VITE_BACKEND_URL=""
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
RUN npm run build

FROM node:20-slim
WORKDIR /app
COPY client/package.json client/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=build /app/dist ./dist

ENV PORT=3000
EXPOSE 3000
CMD ["npm", "run", "start"]
