from fastapi import Query
from typing import Annotated, Optional
from pydantic import BaseModel

class PaginationParams(BaseModel):
    """分页参数模型"""
    page: int
    size: int
    total: Optional[int] = None
    
    def get_skip(self) -> int:
        """获取跳过的记录数"""
        return (self.page - 1) * self.size
    
    def get_limit(self) -> int:
        """获取限制数"""
        return self.size

async def get_pagination_params(
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 10
) -> PaginationParams:
    """获取分页参数依赖项"""
    return PaginationParams(page=page, size=size)

class SortingParams(BaseModel):
    """排序参数模型"""
    sort_by: str
    order: str = "asc"

async def get_sorting_params(
    sort_by: Annotated[str, Query(description="排序字段")] = "id",
    order: Annotated[str, Query(pattern="^(asc|desc)$", description="排序方向")] = "asc"
) -> SortingParams:
    """获取排序参数依赖项"""
    return SortingParams(sort_by=sort_by, order=order) 