from fastapi import APIRouter, Query
from typing import Annotated, Dict, List
from enum import Enum

router = APIRouter(tags=["basic"])

# 定义常用的查询参数类型
SearchQuery = Annotated[str, Query(min_length=3, max_length=50, description="搜索关键词")]
PageSize = Annotated[int, Query(ge=1, le=100, description="每页显示数量")]
SortOrder = Annotated[str, Query(pattern="^(asc|desc)$", description="排序方向")]

# 定义产品类别枚举
class CategoryEnum(str, Enum):
    ELECTRONICS = "electronics"  # 电子产品
    BOOKS = "books"            # 图书
    CLOTHING = "clothing"      # 服装

@router.get("/hello", response_model=Dict[str, str])
async def hello() -> Dict[str, str]:
    """基础的Hello World API"""
    return {"message": "Hello, World From FastAPI", "status": "success"}

@router.get("/world", response_model=Dict[str, str])
async def world() -> Dict[str, str]:
    """另一个Hello World API变体"""
    return {"message": "Hello, World API", "status": "success"}

@router.get("/search")
async def search(
    q: SearchQuery,  # 重用预定义的SearchQuery类型
    page_size: PageSize = 10,  # 重用预定义的PageSize类型
    sort: SortOrder = "asc",   # 重用预定义的SortOrder类型
    filters: Annotated[
        List[str], 
        Query(description="过滤条件", example=["price>100", "rating>4"])
    ] = []
) -> Dict:
    """通用搜索接口"""
    return {
        "query": q,
        "page_size": page_size,
        "sort": sort,
        "filters": filters
    }

@router.get("/orders")
async def get_orders(
    start_date: Annotated[
        str | None, 
        Query(
            pattern=r'^\d{4}-\d{2}-\d{2}$',
            description="开始日期 (YYYY-MM-DD)",
            example="2024-01-01"
        )
    ] = None,
    end_date: Annotated[
        str | None,
        Query(
            pattern=r'^\d{4}-\d{2}-\d{2}$',
            description="结束日期 (YYYY-MM-DD)",
            example="2024-01-31"
        )
    ] = None,
    status: Annotated[
        List[str],
        Query(description="订单状态", example=["pending", "completed"])
    ] = ["pending"]
) -> Dict:
    """获取订单列表"""
    return {
        "start_date": start_date,
        "end_date": end_date,
        "status": status
    } 