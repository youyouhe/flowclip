#!/bin/bash

# Setup script for MySQL database migration

echo "🚀 Setting up MySQL for YouTube Slicer..."
echo "=" * 50

# Check if MySQL is running
if ! command -v mysql &> /dev/null; then
    echo "❌ MySQL client not found. Please install MySQL first."
    exit 1
fi

# Create .env file for MySQL
echo "📄 Creating .env file for MySQL..."
cat > backend/.env << EOF
# Database - MySQL Configuration
DATABASE_URL=mysql+aiomysql://youtube_user:youtube_password@localhost:3307/youtube_slicer

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=youtube-videos
MINIO_SECURE=false

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key-here-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# YouTube API
YOUTUBE_API_KEY=your-youtube-api-key

# Application
DEBUG=true
HOST=0.0.0.0
PORT=8000
RELOAD=true
EOF

echo "✅ .env file created"

# Install MySQL dependencies
echo "📦 Installing MySQL dependencies..."
cd backend
pip install aiomysql pymysql
cd ..

echo ""
echo "🎯 Next steps:"
echo "1. Start MySQL container: docker-compose up -d mysql"
echo "2. Create tables: python migrate_sqlite_to_mysql.py (option 1)"
echo "3. Migrate data (optional): python migrate_sqlite_to_mysql.py (option 2)"
echo "4. Start services: docker-compose up -d"
echo ""
echo "🔧 MySQL configuration:"
echo "   Host: localhost:3307"
echo "   Database: youtube_slicer"
echo "   User: youtube_user"
echo "   Password: youtube_password"

chmod +x setup_mysql.sh