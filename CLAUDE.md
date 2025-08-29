# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube Slicer is a comprehensive video processing platform that downloads YouTube videos, extracts audio, generates transcripts via ASR, and creates video slices based on AI analysis. The system uses FastAPI backend with Celery workers for async processing, MinIO for file storage, and React frontend with real-time WebSocket progress updates.

## Architecture

### Backend Stack
- **FastAPI** with async SQLAlchemy (SQLite/PostgreSQL)
- **Celery** with Redis for task queue and background processing
- **MinIO** for distributed file storage (S3-compatible)
- **OpenAI/LLM** integration for video content analysis
- **FFmpeg** for video/audio processing
- **yt-dlp** for YouTube video downloading

### Frontend Stack
- **React** with TypeScript
- **Ant Design** UI components
- **Zustand** for state management
- **WebSocket** for real-time progress updates
- **Tailwind CSS** for styling

### Key Services
- **Video Download Service**: Downloads YouTube videos with real-time progress
- **Audio Processing**: Extracts and splits audio by silence detection
- **ASR Service**: Generates transcripts using SenseVoice ASR
- **LLM Analysis**: AI-powered video content analysis and slicing
- **Video Slicing**: Creates video segments based on AI analysis

## Development Setup

### Prerequisites
- Python 3.8+
- Node.js 16+
- Redis
- MinIO
- FFmpeg

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-audio.txt

# Start services
docker-compose up -d redis minio

# Run database migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Start Celery worker
celery -A app.core.celery worker --loglevel=info
celery -A app.core.celery beat --loglevel=info  # for scheduled tasks
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev  # Vite dev server
```

## Key Development Commands

### Backend
```bash
# Run tests
pytest tests/
pytest tests/test_video_api.py -v

# Create test user
python create_test_user.py

# Check dependencies
python check_dependencies.py

# Debug specific services
python debug_extract_audio.py
python debug_progress.py
```

### Frontend
```bash
# Development
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

### Docker (Full Stack)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f celery-worker
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/google` - Google OAuth

### Projects
- `GET /api/v1/projects` - List user projects
- `POST /api/v1/projects` - Create project
- `GET /api/v1/projects/{id}` - Get project details

### Videos
- `POST /api/v1/videos/download` - Download YouTube video
- `GET /api/v1/videos` - List videos
- `GET /api/v1/videos/{id}/download-url` - Get MinIO download URL

### Processing
- `POST /api/v1/processing/extract-audio/{video_id}` - Extract audio
- `POST /api/v1/processing/generate-transcript/{video_id}` - Generate transcript
- `POST /api/v1/processing/analyze-with-llm/{video_id}` - AI analysis
- `POST /api/v1/processing/create-slices/{video_id}` - Create video slices

## Core Models

### Database Schema
- **User**: Authentication and user management
- **Project**: Organizes videos into projects
- **Video**: YouTube video metadata and processing status
- **ProcessingTask**: Tracks background processing tasks
- **Transcript**: Generated subtitles and ASR results
- **VideoSlice**: AI-generated video segments
- **LLMAnalysis**: AI analysis results for video content

## Real-time Progress System

### WebSocket Endpoints
- `ws://localhost:8001/ws/progress/{token}` - Real-time progress updates
- Message format includes download_progress, processing_stage, processing_message

### Progress Stages
1. **preparing** (0-5%) - Initial setup
2. **download** (5-50%) - YouTube video download
3. **merging** (50-55%) - Merge audio/video streams
4. **converting** (55-60%) - Format conversion
5. **extract_audio** (60-70%) - Audio extraction
6. **split_audio** (70-80%) - Silence-based audio splitting
7. **asr** (80-90%) - Automatic speech recognition
8. **complete** (100%) - Processing finished

## Testing

### Manual Testing
```bash
# Test YouTube download
curl -X POST http://localhost:8001/api/v1/videos/download \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID", "project_id": 1}'

# Test WebSocket connection
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8001/ws/progress/YOUR_TOKEN
```

### Test Scripts
- `test_complete_flow.py` - End-to-end testing
- `test_progress_tracking.py` - Progress monitoring
- `test_api_commands.md` - API testing commands

## Configuration

### Environment Variables
```bash
# Backend (.env)
DATABASE_URL=sqlite+aiosqlite:///./youtube_slicer.db
REDIS_URL=redis://localhost:6379
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
OPENAI_API_KEY=your_openai_key
YOUTUBE_COOKIES_FILE=/path/to/cookies.txt

# Frontend (.env)
REACT_APP_API_URL=http://localhost:8001
```

## File Structure

```
backend/
├── app/
│   ├── api/v1/           # API endpoints
│   ├── core/            # Configuration, database, celery
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic
│   └── tasks/           # Celery tasks
├── tests/               # Pytest test suite
└── alembic/            # Database migrations

frontend/
├── src/
│   ├── pages/           # React components
│   ├── services/        # API clients
│   ├── components/      # Reusable components
│   └── store/          # State management
└── package.json
```

## Common Issues & Solutions

### Backend
- **FFmpeg not found**: Install system-wide or set FFMPEG_PATH
- **Redis connection**: Check Redis is running on localhost:6379
- **MinIO connection**: Verify MinIO console at http://localhost:9001
- **YouTube cookies**: Use valid cookies.txt for age-restricted content

### Frontend
- **CORS issues**: Backend CORS is configured for localhost:3000
- **WebSocket connection**: Token must be valid JWT
- **Build errors**: Check Node.js version compatibility (16+)

## Production Deployment

### Docker Compose
```bash
# Production deployment
docker-compose -f docker-compose.prod.yml up -d

# Scale Celery workers
docker-compose up -d --scale celery-worker=3
```

### Environment-Specific Config
- **Development**: SQLite, debug mode, auto-reload
- **Production**: PostgreSQL, production secrets, SSL termination