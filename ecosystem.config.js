module.exports = {
  apps: [
    // Backend API
    {
      name: 'flowclip-backend',
      script: '/home/flowclip/EchoClip/venv/bin/python',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level info',
      cwd: '/home/flowclip/EchoClip/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env_file: '/home/flowclip/EchoClip/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/flowclip/EchoClip/backend:/home/flowclip/EchoClip',
        DEBUG: 'false'
      },
      error_file: '/home/flowclip/.pm2/logs/backend-error.log',
      out_file: '/home/flowclip/.pm2/logs/backend-out.log',
      log_file: '/home/flowclip/.pm2/logs/backend-combined.log',
      time: true
    },

    // TUS Callback Server
    {
      name: 'flowclip-callback',
      script: '/home/flowclip/EchoClip/venv/bin/python',
      args: 'callback_server.py',
      cwd: '/home/flowclip/EchoClip/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      env_file: '/home/flowclip/EchoClip/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/flowclip/EchoClip/backend:/home/flowclip/EchoClip',
        CALLBACK_HOST: '0.0.0.0',
        CALLBACK_PORT: '9090',
        REDIS_KEY_PREFIX: 'tus_callback',
        REDIS_RESULT_PREFIX: 'tus_result',
        REDIS_STATS_KEY: 'tus_callback_stats'
      },
      error_file: '/home/flowclip/.pm2/logs/callback-error.log',
      out_file: '/home/flowclip/.pm2/logs/callback-out.log',
      log_file: '/home/flowclip/.pm2/logs/callback-combined.log',
      time: true
    },

    // Celery Worker
    {
      name: 'flowclip-celery-worker',
      script: '/home/flowclip/EchoClip/venv/bin/python',
      args: 'start_celery.py worker --loglevel=info --concurrency=4',
      cwd: '/home/flowclip/EchoClip/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
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

    // Celery Beat
    {
      name: 'flowclip-celery-beat',
      script: '/home/flowclip/EchoClip/venv/bin/python',
      args: 'start_celery.py beat --loglevel=info',
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

    // Frontend (Static Production Server)
    {
      name: 'flowclip-frontend',
      script: '/usr/bin/node',
      args: 'server.js',
      cwd: '/home/flowclip/EchoClip/frontend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      env_file: '/home/flowclip/EchoClip/.env',
      env: {
        NODE_ENV: 'production',
        PORT: '3000'
      },
      error_file: '/home/flowclip/.pm2/logs/frontend-error.log',
      out_file: '/home/flowclip/.pm2/logs/frontend-out.log',
      log_file: '/home/flowclip/.pm2/logs/frontend-combined.log',
      time: true
    },

    // MCP Server
    {
      name: 'flowclip-mcp-server',
      script: '/home/flowclip/EchoClip/venv/bin/python',
      args: 'run_mcp_server_complete.py',
      cwd: '/home/flowclip/EchoClip/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env_file: '/home/flowclip/EchoClip/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/flowclip/EchoClip/backend:/home/flowclip/EchoClip',
        DEBUG: 'false'
      },
      error_file: '/home/flowclip/.pm2/logs/mcp-server-error.log',
      out_file: '/home/flowclip/.pm2/logs/mcp-server-out.log',
      log_file: '/home/flowclip/.pm2/logs/mcp-server-combined.log',
      time: true
    }
  ]
};