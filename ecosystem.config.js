module.exports = {
  apps: [
    {
      name: 'flowclip-backend',
      script: '/home/flowclip/EchoClip/venv/bin/python',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level debug',
      cwd: '/home/flowclip/EchoClip/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env_file: '/home/flowclip/EchoClip/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/flowclip/EchoClip/backend:/home/flowclip/EchoClip'
      },
      error_file: '/home/flowclip/.pm2/logs/backend-error.log',
      out_file: '/home/flowclip/.pm2/logs/backend-out.log',
      log_file: '/home/flowclip/.pm2/logs/backend-combined.log',
      time: true
    },
    {
      name: 'flowclip-celery-worker',
      script: '/home/flowclip/EchoClip/venv/bin/celery',
      args: '-A app.core.celery worker --loglevel=info --concurrency=2',
      cwd: '/home/flowclip/EchoClip/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env_file: '/home/flowclip/EchoClip/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/flowclip/EchoClip/backend:/home/flowclip/EchoClip',
        C_FORCE_ROOT: 'true'
      },
      error_file: '/home/flowclip/.pm2/logs/celery-worker-error.log',
      out_file: '/home/flowclip/.pm2/logs/celery-worker-out.log',
      log_file: '/home/flowclip/.pm2/logs/celery-worker-combined.log',
      time: true,
      kill_timeout: 30000
    },
    {
      name: 'flowclip-celery-beat',
      script: '/home/flowclip/EchoClip/venv/bin/celery',
      args: '-A app.core.celery beat --loglevel=info',
      cwd: '/home/flowclip/EchoClip/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env_file: '/home/flowclip/EchoClip/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/flowclip/EchoClip/backend:/home/flowclip/EchoClip',
        C_FORCE_ROOT: 'true'
      },
      error_file: '/home/flowclip/.pm2/logs/celery-beat-error.log',
      out_file: '/home/flowclip/.pm2/logs/celery-beat-out.log',
      log_file: '/home/flowclip/.pm2/logs/celery-beat-combined.log',
      time: true,
      kill_timeout: 15000
    },
    {
      name: 'flowclip-frontend',
      script: '/usr/bin/npm',
      args: 'run dev',
      cwd: '/home/flowclip/EchoClip/frontend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env_file: '/home/flowclip/EchoClip/.env',
      env: {
        NODE_ENV: 'development',
        REACT_APP_API_URL: 'http://localhost:8001'
      },
      error_file: '/home/flowclip/.pm2/logs/frontend-error.log',
      out_file: '/home/flowclip/.pm2/logs/frontend-out.log',
      log_file: '/home/flowclip/.pm2/logs/frontend-combined.log',
      time: true
    }
  ]
};