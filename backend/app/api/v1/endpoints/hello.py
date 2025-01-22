from enum import Enum
from fastapi import APIRouter, Query # type: ignore
from typing import Annotated, Dict, List

router = APIRouter()

@router.get("/")
async def hello() -> Dict[str, str]:
    return {"message": "Hello, World From FastAPI", "status": "success"}

@router.get("/world")
async def world() -> Dict[str, str]:
    return {"message": "Hello, World API", "status": "success"} 

# 使用 Annotated 定义常用的查询参数类型
SearchQuery = Annotated[str, Query(min_length=3, max_length=50, description="搜索关键词")]
PageSize = Annotated[int, Query(ge=1, le=100, description="每页显示数量")]
SortOrder = Annotated[str, Query(pattern="^(asc|desc)$", description="排序方向")]

# 定义一个枚举类型用于过滤
class CategoryEnum(str, Enum):
    ELECTRONICS = "electronics"
    BOOKS = "books"
    CLOTHING = "clothing"

@router.get("/products")
async def get_products(
    search: SearchQuery,  # 使用前面定义的 Annotated 类型
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    category: Annotated[CategoryEnum | None, Query(description="产品类别")] = None
) -> Dict:
    return {
        "search": search,
        "page": page,
        "category": category
    }

@router.get("/users")
async def get_users(
    # 多个查询参数的例子
    name: Annotated[str | None, Query(min_length=2, description="用户名")] = None,
    age: Annotated[int | None, Query(ge=0, le=150, description="年龄")] = None,
    sort_by: Annotated[List[str], Query(description="排序字段")] = ["created_at"]
) -> Dict:
    return {
        "name": name,
        "age": age,
        "sort_by": sort_by
    }

@router.get("/search")
async def search(
    q: SearchQuery,  # 重用前面定义的 Annotated 类型
    page_size: PageSize = 10,  # 重用前面定义的 Annotated 类型
    sort: SortOrder = "asc",   # 重用前面定义的 Annotated 类型，默认值在这里设置
    filters: Annotated[
        List[str], 
        Query(description="过滤条件", example=["price>100", "rating>4"])
    ] = []
) -> Dict:
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
    return {
        "start_date": start_date,
        "end_date": end_date,
        "status": status
    }