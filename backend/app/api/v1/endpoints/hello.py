from enum import Enum
from fastapi import APIRouter, Query # type: ignore
from typing import Annotated, Dict, List

router = APIRouter()

# 基础Hello World端点
@router.get("/")
async def hello() -> Dict[str, str]:
    """
    基础的Hello World API
    """
    return {"message": "Hello, World From FastAPI", "status": "success"}

# 另一个Hello World变体
@router.get("/world")
async def world() -> Dict[str, str]:
    """
    另一个Hello World API变体
    """
    return {"message": "Hello, World API", "status": "success"} 

# 定义常用的查询参数类型，使用Annotated进行注解
SearchQuery = Annotated[str, Query(min_length=3, max_length=50, description="搜索关键词")]
PageSize = Annotated[int, Query(ge=1, le=100, description="每页显示数量")]
SortOrder = Annotated[str, Query(pattern="^(asc|desc)$", description="排序方向")]

# 定义产品类别枚举
class CategoryEnum(str, Enum):
    ELECTRONICS = "electronics"  # 电子产品
    BOOKS = "books"            # 图书
    CLOTHING = "clothing"      # 服装

# 产品搜索端点
@router.get("/products")
async def get_products(
    search: SearchQuery,  # 使用预定义的SearchQuery类型
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    category: Annotated[CategoryEnum | None, Query(description="产品类别")] = None
) -> Dict:
    """
    获取产品列表
    
    参数说明：
    - search: 搜索关键词，长度3-50
    - page: 页码，从1开始
    - category: 产品类别，可选值：electronics/books/clothing
    """
    return {
        "search": search,
        "page": page,
        "category": category
    }

# 用户搜索端点
@router.get("/users")
async def get_users(
    # 多个查询参数示例
    name: Annotated[str | None, Query(min_length=2, description="用户名")] = None,
    age: Annotated[int | None, Query(ge=0, le=150, description="年龄")] = None,
    sort_by: Annotated[List[str], Query(description="排序字段")] = ["created_at"]
) -> Dict:
    """
    获取用户列表
    
    参数说明：
    - name: 用户名，最小长度2
    - age: 年龄，0-150之间
    - sort_by: 排序字段列表，默认按创建时间排序
    """
    return {
        "name": name,
        "age": age,
        "sort_by": sort_by
    }

# 通用搜索端点
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
    """
    通用搜索接口
    
    参数说明：
    - q: 搜索关键词
    - page_size: 每页显示数量
    - sort: 排序方向（asc/desc）
    - filters: 过滤条件列表，例如：["price>100", "rating>4"]
    """
    return {
        "query": q,
        "page_size": page_size,
        "sort": sort,
        "filters": filters
    }

# 订单查询端点
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
    """
    获取订单列表
    
    参数说明：
    - start_date: 开始日期，格式：YYYY-MM-DD
    - end_date: 结束日期，格式：YYYY-MM-DD
    - status: 订单状态列表，默认为["pending"]
    """
    return {
        "start_date": start_date,
        "end_date": end_date,
        "status": status
    }