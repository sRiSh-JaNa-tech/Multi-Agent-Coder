# Stage 1: Build the React application
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package configurations and install node packages
COPY package*.json ./
RUN npm install

# Copy application source and build
COPY . .
RUN npm run build

# Stage 2: Serve the React application with Nginx
FROM nginx:alpine

# Copy built application to Nginx server path
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy our custom Nginx proxy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# Run Nginx
CMD ["nginx", "-g", "daemon off;"]
