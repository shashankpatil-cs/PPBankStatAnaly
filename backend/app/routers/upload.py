import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from app.auth import get_current_user
from app.config import settings
from app.database import transactions_collection, statements_collection
from app.schemas import UploadResponse, AIStatusResponse
from app.services import s3_service
from app.services.pdf_parser import parse_pdf

router = APIRouter(prefix="/statements", tags=["upload"])

os.makedirs(settings.upload_dir, exist_ok=True)


def suggest_category(counterparty: str) -> str:
    cp = (counterparty or "").lower()
    if any(k in cp for k in ["swiggy", "zomato", "sweets", "restaurant", "cafe", "pizza", "burger", "bakery", "bhojnalaya", "tea", "coffee", "dhaba"]):
        return "Food"
    if any(k in cp for k in ["groceries", "supermarket", "blinkit", "zepto", "instamart", "milk", "dairy", "kirana", "mart", "vegetables", "fruits"]):
        return "Groceries"
    if any(k in cp for k in ["recharge", "electricity", "bill", "airtel", "jio", "vi ", "postpaid", "prepaid", "broadband", "bescom", "msedcl", "gas", "water"]):
        return "Recharge & Bills"
    if any(k in cp for k in ["amazon", "flipkart", "myntra", "meesho", "zara", "clothing"]):
        return "Shopping"
    if any(k in cp for k in ["uber", "ola", "rapido", "irctc", "railway", "metro", "petrol", "fuel", "hpcl", "bpcl", "iocl"]):
        return "Travel"
    if any(k in cp for k in ["pharmacy", "medical", "hospital", "doctor", "apollo", "1mg", "clinic"]):
        return "Health"
    if any(k in cp for k in ["movie", "bookmyshow", "cinema", "netflix", "prime", "hotstar", "spotify"]):
        return "Entertainment"
    if any(k in cp for k in ["zerodha", "groww", "upstox", "mutual fund", "sip"]):
        return "Investment"
    return "Uncategorized"


@router.get("/ai-status", response_model=AIStatusResponse)
async def get_ai_status(current_user: dict = Depends(get_current_user)):
    return AIStatusResponse(
        ai_available=bool(settings.openai_api_key),
        model=settings.openai_model if settings.openai_api_key else "None",
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_statement(
    file: UploadFile = File(...),
    pdf_password: str | None = Form(default=None),
    use_ai: bool = Form(default=True),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    user_id = current_user["_id"]
    statement_id = str(uuid.uuid4())
    local_path = os.path.join(settings.upload_dir, f"{statement_id}.pdf")

    contents = await file.read()
    with open(local_path, "wb") as f:
        f.write(contents)

    try:
        parse_result = await parse_pdf(local_path, password=pdf_password, force_fallback=not use_ai)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {e}")
    finally:
        pass

    s3_key = s3_service.upload_bytes(
        contents, key=f"{user_id}/statements/{statement_id}.pdf", content_type="application/pdf"
    )

    # Clean up previous transactions for the same statement if re-uploaded
    existing_stmts = await statements_collection.find({"user_id": user_id, "filename": file.filename}).to_list(None)
    for old_s in existing_stmts:
        await transactions_collection.delete_many({"statement_id": old_s["_id"], "user_id": user_id})
        await statements_collection.delete_one({"_id": old_s["_id"]})

    if parse_result.transactions:
        docs = []
        for t in parse_result.transactions:
            cat = t.category if (t.category and t.category != "Uncategorized") else suggest_category(t.counterparty)
            doc = {
                "_id": str(uuid.uuid4()),
                "date": t.date,
                "time": t.time,
                "counterparty": t.counterparty,
                "amount": t.amount,
                "type": t.type,
                "description": t.description,
                "category": cat,
                "raw_text": t.raw_text,
                "statement_id": statement_id,
                "user_id": user_id,
            }
            if t.txn_id:
                doc["txn_id"] = t.txn_id
            docs.append(doc)

        if docs:
            try:
                await transactions_collection.insert_many(docs, ordered=False)
            except Exception:
                pass

    await statements_collection.insert_one(
        {
            "_id": statement_id,
            "user_id": user_id,
            "filename": file.filename,
            "uploaded_at": datetime.now(timezone.utc),
            "transactions_extracted": len(parse_result.transactions),
            "transactions_failed_to_parse": len(parse_result.failed_blocks),
            "extraction_method": parse_result.extraction_method,
            "s3_pdf_key": s3_key,
        }
    )

    if os.path.exists(local_path):
        os.remove(local_path)

    return UploadResponse(
        statement_id=statement_id,
        filename=file.filename,
        transactions_extracted=len(parse_result.transactions),
        transactions_failed_to_parse=len(parse_result.failed_blocks),
        extraction_method=parse_result.extraction_method,
        s3_pdf_key=s3_key,
    )


@router.get("")
async def list_statements(current_user: dict = Depends(get_current_user)):
    cursor = statements_collection.find({"user_id": current_user["_id"]}).sort("uploaded_at", -1)
    return await cursor.to_list(length=None)
