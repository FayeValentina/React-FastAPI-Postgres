from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# 作者基本信息模型（防止循环导入）
class UserBasicInfo(BaseModel):
    """用户基本信息，用于帖子响应中"""
    id: int
    username: str
    full_name: Optional[str] = None
    
    # 配置模型，允许从ORM模型创建
    model_config = {"from_attributes": True}


# 帖子基础模型
class PostBase(BaseModel):
    """帖子基础信息"""
    title: str = Field(..., min_length=3, max_length=100)
    content: str = Field(..., min_length=10)
    summary: Optional[str] = Field(None, max_length=200)
    published: bool = False


# 帖子创建模型
class PostCreate(PostBase):
    """创建帖子时的模型"""
    pass


# 帖子更新完整模型
class PostUpdateFull(PostBase):
    """完整更新帖子信息的模型"""
    pass


# 帖子部分更新模型
class PostUpdatePartial(BaseModel):
    """部分更新帖子信息的模型"""
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    content: Optional[str] = Field(None, min_length=10)
    summary: Optional[str] = Field(None, max_length=200)
    published: Optional[bool] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "更新的标题",
                "content": "更新的内容...",
                "summary": "更新的摘要",
                "published": True
            }
        }
    }


# 帖子响应模型
class PostResponse(PostBase):
    """帖子信息响应模型"""
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime

    # 配置模型，允许从ORM模型创建
    model_config = {"from_attributes": True}


# 包含作者信息的详细帖子响应模型
class PostDetailResponse(PostResponse):
    """包含作者信息的详细帖子响应模型"""
    author: UserBasicInfo

    # 配置模型，允许从ORM模型创建
    model_config = {"from_attributes": True} 