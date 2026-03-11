# Use an official Node.js runtime as a parent image
FROM node:22-alpine

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Accept build argument for API URL
ARG VITE_API_BASE_URL
# Set as environment variable so Vite can read it during build
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build the application (Vite will bake VITE_API_BASE_URL into the JS files)
RUN npm run build

# Expose the port the app runs on
EXPOSE 3000

# Start the application
CMD ["npm", "start"]