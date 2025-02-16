from fastapi import HTTPException, status
from typing import Callable, TypeVar, Any
from datetime import datetime

T = TypeVar('T')

def validate_entity_exists(get_entity: Callable[[Any], T | None]) -> Callable[[Any], T]:
    """验证实体是否存在的依赖项工厂函数"""
    async def dependency(entity_id: Any) -> T:
        entity = await get_entity(entity_id)
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity with id {entity_id} not found"
            )
        return entity
    return dependency

def validate_date_range(
    start_date: datetime | None = None,
    end_date: datetime | None = None
) -> tuple[datetime | None, datetime | None]:
    """验证日期范围的依赖项"""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date"
        )
    return start_date, end_date

def validate_price_range(
    min_price: float | None = None,
    max_price: float | None = None
) -> tuple[float | None, float | None]:
    """验证价格范围的依赖项"""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Minimum price must be less than maximum price"
        )
    return min_price, max_price 