FROM node:18-alpine as build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the app with environment variables
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN echo "Building with API URL: $VITE_API_URL" && npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app

# Copy build from build stage
COPY --from=build /app/dist ./dist

# Install serve to serve the build
RUN npm install -g serve

# Expose port
EXPOSE 3000

# Start the app
CMD ["serve", "-s", "dist", "-l", "3000"]