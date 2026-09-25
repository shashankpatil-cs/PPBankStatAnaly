from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

from app.auth import get_current_user
from app.database import transactions_collection
from app.schemas import TransactionUpdate
from app.services import analytics, s3_service
from app.config import settings
import uuid

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _build_query(
    user_id: str,
    search: Optional[str],
    txn_type: Optional[str],
    category: Optional[str],
    min_amount: Optional[float],
    max_amount: Optional[float],
    start_date: Optional[date],
    end_date: Optional[date],
):
    query: dict = {"user_id": user_id}
    if search:
        query["$or"] = [
            {"counterparty": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"txn_id": {"$regex": search, "$options": "i"}},
        ]
    if txn_type:
        query["type"] = txn_type
    if category:
        query["category"] = category
    if min_amount is not None or max_amount is not None:
        amt = {}
        if min_amount is not None:
            amt["$gte"] = min_amount
        if max_amount is not None:
            amt["$lte"] = max_amount
        query["amount"] = amt
    if start_date or end_date:
        d = {}
        if start_date:
            d["$gte"] = start_date.isoformat()
        if end_date:
            d["$lte"] = end_date.isoformat()
        query["date"] = d
    return query


@router.get("")
async def list_transactions(
    current_user: dict = Depends(get_current_user),
    search: Optional[str] = Query(None, description="Search counterparty name"),
    txn_type: Optional[str] = Query(None, pattern="^(DEBIT|CREDIT)$"),
    category: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sort_by: str = Query("date", pattern="^(date|amount)$"),
    sort_dir: int = Query(-1, ge=-1, le=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    query = _build_query(
        current_user["_id"], search, txn_type, category, min_amount, max_amount, start_date, end_date
    )
    total = await transactions_collection.count_documents(query)
    cursor = (
        transactions_collection.find(query)
        .sort(sort_by, sort_dir)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = await cursor.to_list(length=None)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.patch("/{txn_id}")
async def update_transaction(txn_id: str, payload: TransactionUpdate, current_user: dict = Depends(get_current_user)):
    user_id = current_user["_id"]
    update_data = {
        k: v for k, v in payload.model_dump().items()
        if v is not None and k != "update_all_matching"
    }
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    orig = await transactions_collection.find_one({"_id": txn_id, "user_id": user_id})
    if not orig:
        raise HTTPException(status_code=404, detail="Transaction not found")

    result = await transactions_collection.update_one(
        {"_id": txn_id, "user_id": user_id}, {"$set": update_data}
    )

    updated_count = 1
    # If requested, apply counterparty and category to all other transactions with the same original counterparty
    if payload.update_all_matching and orig.get("counterparty"):
        batch_fields = {}
        if payload.counterparty is not None:
            batch_fields["counterparty"] = payload.counterparty
        if payload.category is not None:
            batch_fields["category"] = payload.category
        if payload.description is not None:
            batch_fields["description"] = payload.description

        if batch_fields:
            batch_res = await transactions_collection.update_many(
                {"user_id": user_id, "counterparty": orig["counterparty"]},
                {"$set": batch_fields},
            )
            updated_count = batch_res.modified_count

    return {"status": "updated", "updated_count": updated_count}


@router.get("/categories/list")
async def list_user_categories(current_user: dict = Depends(get_current_user)):
    """Return distinct categories present in user's transactions."""
    cats = await transactions_collection.distinct("category", {"user_id": current_user["_id"]})
    defaults = ["Person", "Friend", "Groceries", "Food", "Shopping", "Recharge & Bills", "Entertainment", "Health", "Travel", "Investment", "Family"]
    # Combine user's existing categories with defaults
    combined = sorted(list(set(defaults + [c for c in cats if c and c != "Uncategorized"])))
    return {"categories": combined}


@router.delete("/{txn_id}")
async def delete_transaction(txn_id: str, current_user: dict = Depends(get_current_user)):
    result = await transactions_collection.delete_one({"_id": txn_id, "user_id": current_user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"status": "deleted"}


@router.get("/export/csv")
async def export_csv(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    query = _build_query(current_user["_id"], None, None, None, None, None, start_date, end_date)
    docs = await transactions_collection.find(query).sort("date", -1).to_list(length=None)
    df = analytics.transactions_to_df(docs)
    csv_bytes = analytics.to_csv_bytes(df)

    # Also archive the export to S3 for the user's records
    s3_service.upload_bytes(
        csv_bytes,
        key=f"{current_user['_id']}/exports/{uuid.uuid4()}.csv",
        content_type="text/csv",
    )

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )
