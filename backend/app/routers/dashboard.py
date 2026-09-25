from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.database import transactions_collection
from app.services import analytics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _user_df(user_id: str, start_date: Optional[date], end_date: Optional[date]):
    query: dict = {"user_id": user_id}
    if start_date or end_date:
        d = {}
        if start_date:
            d["$gte"] = start_date.isoformat()
        if end_date:
            d["$lte"] = end_date.isoformat()
        query["date"] = d
    docs = await transactions_collection.find(query).to_list(length=None)
    return analytics.transactions_to_df(docs)


@router.get("/summary")
async def summary(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    df = await _user_df(current_user["_id"], start_date, end_date)
    return analytics.compute_summary(df)


@router.get("/top-recipients")
async def top_recipients(
    current_user: dict = Depends(get_current_user),
    n: int = Query(10, ge=1, le=50),
    txn_type: str = Query("DEBIT", pattern="^(DEBIT|CREDIT)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    df = await _user_df(current_user["_id"], start_date, end_date)
    return analytics.top_recipients(df, n, txn_type)


@router.get("/trend")
async def trend(
    current_user: dict = Depends(get_current_user),
    granularity: Literal["daily", "monthly"] = "daily",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    df = await _user_df(current_user["_id"], start_date, end_date)
    return analytics.trend(df, granularity)


@router.get("/categories")
async def categories(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    df = await _user_df(current_user["_id"], start_date, end_date)
    return analytics.category_breakdown(df)
