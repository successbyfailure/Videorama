# Videorama v2.0.0 - Frontend Dockerfile

FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Create .vite directory and set permissions for non-root users
RUN mkdir -p /app/node_modules/.vite && \
    chmod -R 777 /app/node_modules/.vite

# Expose port
EXPOSE 5173

# Run development server
CMD ["npm", "run", "dev"]
