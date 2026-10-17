# Stage 2: Build the Backend
FROM node:20-bookworm-slim

# Install system dependencies: Python, FFmpeg, 7-Zip, and Tesseract
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    p7zip-full \
    tesseract-ocr \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links so that 'py' and 'python' resolve to 'python3'
RUN ln -sf /usr/bin/python3 /usr/bin/py && ln -sf /usr/bin/python3 /usr/bin/python

# Create application directory
WORKDIR /usr/src/app

# Copy package descriptors and install production dependencies
COPY package*.json .
RUN npm install

# Copy Python requirements and install globally
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy backend codebase
COPY . .


# Set default env variables
ENV PORT=3000
ENV NODE_ENV=production

# Expose the service port
EXPOSE 3000

# Command to run the application directly, bypassing redundant runtime setup
CMD ["node", "src/server.js"]
