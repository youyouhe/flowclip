#!/bin/bash

# Complete MySQL setup and migration script

echo "🚀 Complete MySQL Setup for YouTube Slicer"
echo "=" * 50

# Step 1: Start MySQL container
echo "📦 Starting MySQL container..."
docker-compose up -d mysql

# Wait for MySQL to be ready
echo "⏳ Waiting for MySQL to be ready..."
sleep 10

# Check if MySQL is running
if ! docker-compose ps | grep mysql | grep -q "Up"; then
    echo "❌ MySQL container failed to start"
    exit 1
fi

echo "✅ MySQL container is running"

# Step 2: Install Python MySQL dependencies
echo "📦 Installing MySQL Python dependencies..."
cd backend
pip install aiomysql pymysql
cd ..

# Step 3: Create tables and migrate data
echo "🔧 Creating MySQL tables..."
python fix_migration.py

echo ""
echo "🎯 Next steps:"
echo "1. Check MySQL container: docker-compose logs mysql"
echo "2. Start all services: docker-compose up -d"
echo "3. Test the application"
echo ""
echo "📊 MySQL is ready on localhost:3307"

chmod +x setup_mysql_complete.sh