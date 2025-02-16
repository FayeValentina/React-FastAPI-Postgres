from pydantic import BaseModel, Field
from typing import List, Optional, Dict

# 文件上传响应模型
class FileUploadResponse(BaseModel):
    """文件上传响应模型"""
    filename: str
    content_type: str
    file_size: int
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "filename": "test.pdf",
                "content_type": "application/pdf",
                "file_size": 1024,
                "description": "Test document",
                "tags": ["document", "test"]
            }
        }
    }

# 多文件上传响应模型
class MultipleFilesResponse(BaseModel):
    """多文件上传响应模型"""
    file_sizes: List[int]
    fileb_size: int
    message: str
    total_size: int

# 带元数据的文件上传响应模型
class FileWithMetadataResponse(BaseModel):
    """带元数据的文件上传响应模型"""
    filename: str
    content_type: str
    description: Optional[str] = None
    file_size: int
    first_bytes: str
    message: str 