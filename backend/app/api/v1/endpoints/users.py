# 导入必要的模块
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

# 导入相关的模型和CRUD操作
from app.schemas.user import UserCreate, UserResponse
from app.crud import user as user_crud
from app.dependencies.db import get_db

# 创建路由器
router = APIRouter()
# 创建日志记录器
logger = logging.getLogger(__name__)


@router.post("/users", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    创建新用户
    
    参数说明：
    - user_data: 用户创建数据，包含邮箱、用户名、密码等信息
    - db: 数据库会话，通过依赖注入获取
    
    返回：
    - 创建成功的用户信息
    
    异常：
    - 400: 用户数据验证失败
    - 500: 服务器内部错误
    """
    try:
        # 调用CRUD操作创建用户
        user = await user_crud.create_user(db, user_data)
        return user
    except ValueError as e:
        # 处理验证错误
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        # 记录意外错误
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while creating user"
        ) 