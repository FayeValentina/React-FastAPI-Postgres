from enum import Enum
from fastapi import APIRouter, Query # type: ignore
from typing import Annotated, Dict, List

router = APIRouter()

# 基础Hello World端点
@router.get("/",
    response_model=Dict[str, str],
    tags=["hello"],
    summary="基础Hello World",
    description="返回一个简单的Hello World消息",
    responses={
        200: {"description": "成功返回问候消息"}
    }
)
async def hello() -> Dict[str, str]:
    """
    基础的Hello World API
    """
    return {"message": "Hello, World From FastAPI", "status": "success"}

# 另一个Hello World变体
@router.get("/world",
    response_model=Dict[str, str],
    tags=["hello"],
    summary="Hello World变体",
    description="返回另一个版本的Hello World消息",
    responses={
        200: {"description": "成功返回问候消息"}
    }
)
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
@router.get("/products",
    response_model=Dict,
    tags=["products"],
    summary="获取产品列表",
    description="根据搜索条件获取产品列表，支持分页和类别筛选",
    responses={
        200: {"description": "成功获取产品列表"},
        400: {"description": "无效的查询参数"},
        404: {"description": "未找到匹配的产品"}
    }
)
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
@router.get("/users",
    response_model=Dict,
    tags=["users"],
    summary="获取用户列表",
    description="获取用户列表，支持按名称和年龄筛选，以及自定义排序",
    responses={
        200: {"description": "成功获取用户列表"},
        400: {"description": "无效的查询参数"}
    }
)
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
@router.get("/search",
    response_model=Dict,
    tags=["search"],
    summary="通用搜索接口",
    description="提供通用搜索功能，支持分页、排序和过滤条件",
    responses={
        200: {"description": "搜索成功"},
        400: {"description": "无效的搜索参数"},
        422: {"description": "无效的过滤条件格式"}
    }
)
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
@router.get("/orders",
    response_model=Dict,
    tags=["orders"],
    summary="获取订单列表",
    description="获取订单列表，支持日期范围和状态筛选",
    responses={
        200: {"description": "成功获取订单列表"},
        400: {"description": "无效的日期格式或状态值"},
        404: {"description": "未找到匹配的订单"}
    }
)
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