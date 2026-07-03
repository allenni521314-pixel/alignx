from fastapi import APIRouter, Depends

from dependencies.auth import get_current_user
from schemas.advertising_strategy import AdvertisingStrategyInput, AdvertisingStrategyOutput
from schemas.auth import UserResponse
from services.advertising_strategy_engine import advertising_strategy_engine


router = APIRouter(prefix="/api/v1/advertising-strategy", tags=["advertising-strategy"])


@router.get("/schema", response_model=AdvertisingStrategyOutput)
async def get_advertising_strategy_schema(_current_user: UserResponse = Depends(get_current_user)):
    return advertising_strategy_engine.build_schema()


@router.post("/evaluate", response_model=AdvertisingStrategyOutput)
async def evaluate_advertising_strategy(
    payload: AdvertisingStrategyInput,
    _current_user: UserResponse = Depends(get_current_user),
):
    return advertising_strategy_engine.evaluate(payload)
