"""
MongoDB connection (Motor async client) + index setup.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db_name]

transactions_collection = db["transactions"]
statements_collection = db["statements"]   # one doc per uploaded PDF (metadata)
users_collection = db["users"]


async def init_indexes():
    """Call once on app startup."""
    await transactions_collection.create_index([("user_id", 1), ("date", -1)])
    await transactions_collection.create_index([("user_id", 1), ("statement_id", 1)])
    await transactions_collection.create_index(
        [("user_id", 1), ("txn_id", 1), ("type", 1)], unique=True, sparse=True
    )
    await statements_collection.create_index([("user_id", 1), ("uploaded_at", -1)])
    await users_collection.create_index("email", unique=True)
