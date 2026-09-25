"""
AI Financial Assistant, built on the OpenAI Agents SDK.

The agent never sees raw data unprompted — it calls function tools that
query MongoDB (scoped to the current user_id) on demand, so answers are
always grounded in the user's actual stored transactions rather than the
model's own guesses.

Docs: https://openai.github.io/openai-agents-python/
"""
import json
from typing import Optional

from agents import Agent, Runner, function_tool, set_default_openai_key

from app.config import settings
from app.database import transactions_collection
from app.services import analytics

import os
if settings.openai_api_key:
    _key = settings.openai_api_key.strip()
    os.environ["OPENAI_API_KEY"] = _key
    set_default_openai_key(_key)


async def _fetch_user_df(user_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    query = {"user_id": user_id}
    if start_date or end_date:
        date_q = {}
        if start_date:
            date_q["$gte"] = start_date
        if end_date:
            date_q["$lte"] = end_date
        query["date"] = date_q
    docs = await transactions_collection.find(query).to_list(length=None)
    return analytics.transactions_to_df(docs)


def build_tools(user_id: str):
    """Tools are closed over the authenticated user_id so the model can
    never be tricked (via prompt injection in a message) into reading
    another user's data — there's no user_id parameter for it to set."""

    @function_tool
    async def get_financial_summary(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """Get total spent, total received, net cash flow, average spent per day (calendar basis),
        average spent per month, and transaction counts, optionally filtered to a date range (YYYY-MM-DD)."""
        df = await _fetch_user_df(user_id, start_date, end_date)
        return json.dumps(analytics.compute_summary(df))

    @function_tool
    async def get_top_recipients(n: int = 5) -> str:
        """Get the top N recipients by total money sent to them (debits)."""
        df = await _fetch_user_df(user_id)
        return json.dumps(analytics.top_recipients(df, n))

    @function_tool
    async def get_spending_trend(granularity: str = "monthly") -> str:
        """Get spending/received trend over time. granularity is
        'daily' or 'monthly'."""
        df = await _fetch_user_df(user_id)
        g = granularity if granularity in ("daily", "monthly") else "monthly"
        return json.dumps(analytics.trend(df, g))

    @function_tool
    async def search_transactions(
        query_text: Optional[str] = None,
        category: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        txn_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Search/filter the user's transactions. query_text matches against
        the counterparty name (case-insensitive substring). category filters by
        spending category like 'Person', 'Friend', 'Groceries', 'Food', etc. txn_type is
        'DEBIT' or 'CREDIT' if given."""
        mongo_query: dict = {"user_id": user_id}
        if query_text:
            mongo_query["$or"] = [
                {"counterparty": {"$regex": query_text, "$options": "i"}},
                {"description": {"$regex": query_text, "$options": "i"}},
                {"txn_id": {"$regex": query_text, "$options": "i"}},
            ]
        if category:
            mongo_query["category"] = {"$regex": category, "$options": "i"}
        if txn_type in ("DEBIT", "CREDIT"):
            mongo_query["type"] = txn_type
        if min_amount is not None or max_amount is not None:
            amt_q = {}
            if min_amount is not None:
                amt_q["$gte"] = min_amount
            if max_amount is not None:
                amt_q["$lte"] = max_amount
            mongo_query["amount"] = amt_q
        if start_date or end_date:
            date_q = {}
            if start_date:
                date_q["$gte"] = start_date
            if end_date:
                date_q["$lte"] = end_date
            mongo_query["date"] = date_q

        cursor = transactions_collection.find(mongo_query, {"_id": 0}).sort("date", -1).limit(min(limit, 100))
        docs = await cursor.to_list(length=None)
        return json.dumps(docs, default=str)

    @function_tool
    async def get_category_breakdown() -> str:
        """Get total spend grouped by category."""
        df = await _fetch_user_df(user_id)
        return json.dumps(analytics.category_breakdown(df))

    return [
        get_financial_summary,
        get_top_recipients,
        get_spending_trend,
        search_transactions,
        get_category_breakdown,
    ]


def build_agent(user_id: str) -> Agent:
    return Agent(
        name="PhonePe Financial Assistant",
        instructions=(
            "You are a personal financial assistant analyzing the user's PhonePe "
            "transaction history. Always call the relevant tool to fetch real data "
            "before answering questions about amounts, recipients, trends, or "
            "specific transactions — never estimate or invent numbers. Amounts are "
            "in INR (₹). Keep answers concise and use the actual figures returned "
            "by the tools. If the tools return no data, say so plainly."
        ),
        model=settings.openai_model,
        tools=build_tools(user_id),
    )


async def chat(user_id: str, message: str, conversation_history: Optional[list] = None) -> str:
    agent = build_agent(user_id)
    input_items = conversation_history or []
    input_items = input_items + [{"role": "user", "content": message}]
    result = await Runner.run(agent, input_items)
    return result.final_output
