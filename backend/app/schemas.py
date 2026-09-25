from datetime import datetime, date as date_type
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, EmailStr


# ---------- Auth ----------

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str


# ---------- Transactions ----------

TxnType = Literal["DEBIT", "CREDIT"]


class Transaction(BaseModel):
    txn_id: Optional[str] = None          # PhonePe transaction ID, if extracted
    date: date_type
    time: Optional[str] = None            # "05:30 PM" as printed on statement
    datetime_iso: Optional[datetime] = None
    counterparty: str                     # "Paid to X" / "Received from X"
    amount: float
    type: TxnType
    description: Optional[str] = None     # Description or purpose of transaction
    category: Optional[str] = "Uncategorized"
    raw_text: Optional[str] = None        # original block, for debugging/audit
    statement_id: str
    user_id: str

    class Config:
        json_encoders = {date_type: lambda d: d.isoformat()}


class TransactionOut(Transaction):
    id: str = Field(alias="_id")

    class Config:
        populate_by_name = True
        json_encoders = {date_type: lambda d: d.isoformat()}


class TransactionUpdate(BaseModel):
    counterparty: Optional[str] = None
    amount: Optional[float] = None
    type: Optional[TxnType] = None
    category: Optional[str] = None
    description: Optional[str] = None
    update_all_matching: Optional[bool] = False


# ---------- Dashboard ----------

class DashboardSummary(BaseModel):
    total_spent: float
    total_received: float
    actual_spent: Optional[float] = 0.0
    net_cash_flow: float
    net_outflow: Optional[float] = 0.0
    transaction_count: int
    debit_count: int
    credit_count: int
    date_range: Optional[dict] = None
    avg_spent_per_day: Optional[float] = 0.0
    avg_spent_per_month: Optional[float] = 0.0
    months_count: Optional[int] = 0
    total_calendar_days: Optional[int] = 0


class TopRecipient(BaseModel):
    counterparty: str
    total_amount: float
    transaction_count: int


class TrendPoint(BaseModel):
    period: str   # "2024-01-15" (daily) or "2024-01" (monthly)
    spent: float
    received: float


# ---------- Upload ----------

class UploadResponse(BaseModel):
    statement_id: str
    filename: str
    transactions_extracted: int
    transactions_failed_to_parse: int
    extraction_method: Optional[str] = "ai"  # "ai" or "regex_fallback"
    s3_pdf_key: Optional[str] = None


class AIStatusResponse(BaseModel):
    ai_available: bool
    model: str


# ---------- AI Extraction Validation ----------

class ExtractedTransactionValidation(BaseModel):
    date: str
    time: Optional[str] = None
    type: str
    counterparty: str
    amount: float
    description: Optional[str] = None
    txn_id: Optional[str] = None
    category: Optional[str] = "Uncategorized"
    raw_text: Optional[str] = None


# ---------- AI Assistant ----------

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
