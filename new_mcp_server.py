import logging
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from jose import jwt
import datetime
from pydantic import BaseModel

# 设置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Received request: {request.method} {request.url}")
    logger.debug(f"Headers: {dict(request.headers)}")
    
    try:
        body = await request.body()
        logger.debug(f"Body: {body.decode() if body else 'No body'}")
    except Exception as e:
        logger.debug(f"Could not read body: {e}")
    
    response = await call_next(request)
    logger.debug(f"Response status: {response.status_code}")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"

security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

def create_token(username: str) -> str:
    payload = {
        "username": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        return username
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

@app.post("/login")
async def login(request: LoginRequest):
    if request.username == "demo" and request.password == "demo":
        token = create_token(request.username)
        return {"access_token": token, "token_type": "bearer"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

@app.get("/hello")
async def hello_world(username: str = Depends(verify_token)):
    return {"message": f"Hello World! Welcome {username}"}

@app.get("/public/info")
async def public_info():
    return {"message": "This is a public endpoint", "version": "1.0.0"}

# 创建MCP服务器实例
mcp = FastApiMCP(app)

# 挂载MCP服务器到FastAPI应用（使用HTTP传输）
mcp.mount_http()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9090)
