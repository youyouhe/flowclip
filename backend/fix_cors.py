#!/usr/bin/env python3
"""
添加CORS配置到现有的FastAPI应用，以解决前端跨域请求问题
"""

import sys
import os
from pathlib import Path

# 添加当前目录到路径
sys.path.append(str(Path('.').absolute()))

from app.main import app
from fastapi.middleware.cors import CORSMiddleware

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源（在生产环境中应该限制为特定域名）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

if __name__ == "__main__":
    print("CORS中间件已添加到FastAPI应用。")
    print("请重启API服务器以应用更改。")
    
    # 打印运行API服务器的命令
    print("\n运行API服务器的命令:")
    print("uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload")