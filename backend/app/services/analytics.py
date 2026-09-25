"""
All financial calculations run through pandas here, off a single source of
truth (the user's transactions from Mongo), so the dashboard numbers, the
top-recipients list, the trend charts, and the AI assistant's answers can
never disagree with each other.
"""
from io import StringIO
from typing import List, Literal, Optional

import pandas as pd


def transactions_to_df(transactions: List[dict]) -> pd.DataFrame:
    if not transactions:
        return pd.DataFrame(
            columns=["date", "time", "counterparty", "amount", "type", "description", "category", "txn_id"]
        )
    df = pd.DataFrame(transactions)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    return df


def compute_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "total_spent": 0.0,
            "total_received": 0.0,
            "actual_spent": 0.0,
            "net_cash_flow": 0.0,
            "transaction_count": 0,
            "debit_count": 0,
            "credit_count": 0,
            "date_range": None,
            "avg_spent_per_day": 0.0,
            "avg_spent_per_month": 0.0,
            "months_count": 0,
            "total_calendar_days": 0,
        }

    debit = df[df["type"] == "DEBIT"]
    credit = df[df["type"] == "CREDIT"]
    total_spent = round(float(debit["amount"].sum()), 2)
    total_received = round(float(credit["amount"].sum()), 2)

    # Formula: actual spent = spent - received
    actual_spent = max(0.0, round(total_spent - total_received, 2))

    min_date = df["date"].min()
    max_date = df["date"].max()

    import calendar
    from datetime import date as dt_date, datetime as dt_datetime

    # Calculate span of months (inclusive)
    months_count = max(1, (max_date.year - min_date.year) * 12 + (max_date.month - min_date.month) + 1)

    start_month_first = dt_date(min_date.year, min_date.month, 1)
    last_day_of_end_month = calendar.monthrange(max_date.year, max_date.month)[1]
    end_month_last = dt_date(max_date.year, max_date.month, last_day_of_end_month)
    total_calendar_days = max(1, (end_month_last - start_month_first).days + 1)

    # Formula: actual_spent / 30 per month span for daily, actual_spent / months_count for monthly
    avg_spent_per_day = round(actual_spent / (months_count * 30), 2)
    avg_spent_per_month = round(actual_spent / months_count, 2)

    return {
        "total_spent": total_spent,
        "total_received": total_received,
        "actual_spent": actual_spent,
        "net_cash_flow": round(total_received - total_spent, 2),
        "transaction_count": int(len(df)),
        "debit_count": int(len(debit)),
        "credit_count": int(len(credit)),
        "date_range": {
            "from": min_date.date().isoformat(),
            "to": max_date.date().isoformat(),
            "formatted_from": min_date.strftime("%d %b %Y"),
            "formatted_to": max_date.strftime("%d %b %Y"),
            "calendar_start": start_month_first.isoformat(),
            "calendar_end": end_month_last.isoformat(),
        },
        "avg_spent_per_day": avg_spent_per_day,
        "avg_spent_per_month": avg_spent_per_month,
        "months_count": months_count,
        "total_calendar_days": total_calendar_days,
    }


def top_recipients(df: pd.DataFrame, n: int = 10, txn_type: str = "DEBIT") -> List[dict]:
    if df.empty:
        return []
    filtered = df[df["type"] == txn_type]
    if filtered.empty:
        return []
    grouped = (
        filtered.groupby("counterparty")["amount"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "total_amount", "count": "transaction_count"})
        .sort_values("total_amount", ascending=False)
        .head(n)
    )
    return [
        {
            "counterparty": idx,
            "total_amount": round(float(row["total_amount"]), 2),
            "transaction_count": int(row["transaction_count"]),
        }
        for idx, row in grouped.iterrows()
    ]


def trend(df: pd.DataFrame, granularity: Literal["daily", "monthly"] = "daily") -> List[dict]:
    if df.empty:
        return []
    period_fmt = "%Y-%m-%d" if granularity == "daily" else "%Y-%m"
    tmp = df.copy()
    tmp["period"] = tmp["date"].dt.strftime(period_fmt)

    pivot = (
        tmp.groupby(["period", "type"])["amount"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    for col in ("DEBIT", "CREDIT"):
        if col not in pivot.columns:
            pivot[col] = 0.0

    pivot = pivot.sort_values("period")
    out = []
    from datetime import datetime
    for _, row in pivot.iterrows():
        p_str = row["period"]
        if granularity == "monthly":
            dt_obj = datetime.strptime(p_str, "%Y-%m")
            label = dt_obj.strftime("%b %Y")  # e.g. 'Apr 2026' (Month AND Year!)
        else:
            dt_obj = datetime.strptime(p_str, "%Y-%m-%d")
            label = dt_obj.strftime("%d %b %Y")  # e.g. '01 Apr 2026'

        out.append({
            "period": p_str,
            "label": label,
            "spent": round(float(row["DEBIT"]), 2),
            "received": round(float(row["CREDIT"]), 2),
        })
    return out


def category_breakdown(df: pd.DataFrame) -> List[dict]:
    if df.empty:
        return []
    debit = df[df["type"] == "DEBIT"].copy()
    debit["category"] = debit.get("category", "Uncategorized").fillna("Uncategorized")
    grouped = debit.groupby("category")["amount"].sum().sort_values(ascending=False)
    return [{"category": idx, "total_amount": round(float(v), 2)} for idx, v in grouped.items()]


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    export_cols = ["date", "time", "counterparty", "description", "type", "amount", "category", "txn_id"]
    cols = [c for c in export_cols if c in df.columns]
    buf = StringIO()
    df[cols].to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
