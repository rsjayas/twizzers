FROM node:22-bookworm-slim

# Chromium runtime libraries (needed by Remotion's headless browser) and fonts.
# fonts-noto-core covers Indian scripts such as Devanagari; the color emoji font
# is for emoji in poems.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libdbus-1-3 libatk1.0-0 libgbm1 libasound2 libxrandr2 libxkbcommon0 \
    libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 \
    libcairo2 libcups2 libxshmfence1 ca-certificates \
    fonts-noto-core fonts-noto-color-emoji fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY src ./src

# Download Remotion's headless Chrome at build time so the first job isn't slow.
RUN npx remotion browser ensure

ENV PORT=4000 OUTPUT_DIR=/tmp/renders
EXPOSE 4000
CMD ["node", "src/server.mjs"]
