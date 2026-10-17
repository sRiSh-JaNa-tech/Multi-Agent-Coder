FROM node:20-alpine

WORKDIR /usr/src/app

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

# Create volume mount point for SQLite data file
RUN mkdir -p /data

EXPOSE 5000

ENV PORT=5000
ENV NODE_ENV=production
ENV SQLITE_DB_PATH=/data/filewiz.sqlite

CMD ["node", "src/server.js"]
