#!/bin/bash

echo "Starting EBookAI Development Environment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env file and add your OpenAI API key"
fi

# Build and start services
echo "Building and starting Docker containers..."
cd docker
docker-compose -f docker-compose.dev.yml up --build -d

echo "Waiting for services to start..."
sleep 10

echo "Services started:"
echo "- Backend API: http://localhost:8000"
echo "- Frontend: http://localhost:3000"
echo "- Calibre Web: http://localhost:8080"

echo "To view logs:"
echo "  docker-compose logs -f backend"
echo "  docker-compose logs -f frontend"

echo "To stop services:"
echo "  cd docker && docker-compose -f docker-compose.dev.yml down"