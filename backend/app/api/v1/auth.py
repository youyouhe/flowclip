from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.user import User
from app.core.security import create_access_token, verify_password, get_password_hash, get_current_user
from pydantic import BaseModel, EmailStr
from typing import Optional, Union

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

class UserCreate(BaseModel):
    """用户创建请求模型"""
    email: EmailStr = None
    username: str = None
    password: str = None
    full_name: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "username": "example_user",
                "password": "secure_password123",
                "full_name": "Example User"
            }
        }

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    """认证令牌响应模型"""
    access_token: str
    token_type: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }

@router.post("/register", response_model=UserResponse, summary="用户注册", description="注册新用户账户", operation_id="register")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """注册新用户
    
    注册一个新的用户账户。邮箱和用户名必须唯一。
    
    Args:
        user_data (UserCreate): 包含用户注册信息的请求体
            - email (EmailStr): 用户邮箱地址，必须唯一
            - username (str): 用户名，必须唯一
            - password (str): 用户密码
            - full_name (Optional[str]): 用户全名
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        UserResponse: 注册成功的用户信息
    
    Raises:
        HTTPException:
            - 400: 邮箱已注册或用户名已被占用
    """
    # Check if user exists
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    stmt = select(User).where(User.username == user_data.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user

@router.post("/login", response_model=Token, summary="用户登录", description="使用用户名和密码登录系统", operation_id="login")
async def login(
    login_data: Optional[UserLogin] = None,
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """用户登录

    使用用户名和密码进行身份验证并获取访问令牌。支持JSON和表单两种格式。

    Args:
        login_data (Optional[UserLogin]): JSON格式的登录数据
        username (Optional[str]): 表单格式的用户名
        password (Optional[str]): 表单格式的密码
        db (AsyncSession): 数据库会话依赖

    Returns:
        Token: 包含访问令牌和令牌类型的响应
            - access_token (str): JWT访问令牌
            - token_type (str): 令牌类型，通常为"bearer"

    Raises:
        HTTPException:
            - 401: 用户名或密码错误
            - 400: 用户账户已被禁用或请求数据无效
    """
    # 处理JSON格式和表单格式数据
    if login_data:
        # JSON格式数据
        username_val = login_data.username
        password_val = login_data.password
    elif username and password:
        # 表单格式数据
        username_val = username
        password_val = password
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request format. Provide username and password as JSON or form data."
        )

    stmt = select(User).where(User.username == username_val)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password_val, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse, summary="获取当前用户信息", description="获取当前已认证用户的信息", operation_id="get_current_user")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息
    
    获取当前已认证用户的信息。需要有效的JWT访问令牌。
    
    Args:
        current_user (User): 通过JWT令牌验证的当前用户依赖
    
    Returns:
        UserResponse: 当前用户的信息
            - id (int): 用户ID
            - email (str): 用户邮箱
            - username (str): 用户名
            - full_name (Optional[str]): 用户全名
            - avatar_url (Optional[str]): 用户头像URL
            - is_active (bool): 用户账户是否激活
    """
    return current_user