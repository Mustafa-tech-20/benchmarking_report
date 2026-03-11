"""
MongoDB Database Connection and User Management
Industry-standard async MongoDB integration with Motor
"""

import os
import logging
import certifi
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError, PyMongoError

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "car_benchmarking_rbac")
USERS_COLLECTION = "users"
CONVERSATIONS_COLLECTION = "conversations"

# Validate MongoDB URL
if not MONGODB_URL:
    logger.error("MONGODB_URL not found in environment variables!")
    raise ValueError("MONGODB_URL environment variable is required")

# Global MongoDB client
_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongodb():
    """
    Initialize MongoDB connection with SSL certificate verification

    Should be called on application startup
    """
    global _client, _database

    try:
        logger.info(f"Connecting to MongoDB Atlas...")
        logger.info(f"Database: {DATABASE_NAME}")
        
        # Create client with SSL certificate verification using certifi
        _client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            tlsCAFile=certifi.where()  # SSL certificate for Atlas
        )

        # Verify connection
        await _client.admin.command('ping')

        _database = _client[DATABASE_NAME]

        # Create indexes
        await _database[USERS_COLLECTION].create_index("email", unique=True)
        await _database[CONVERSATIONS_COLLECTION].create_index([("user_email", 1), ("updated_at", -1)])
        await _database[CONVERSATIONS_COLLECTION].create_index("conversation_id", unique=True)

        logger.info(f"✓ Successfully connected to MongoDB: {DATABASE_NAME}")
        return _database

    except Exception as e:
        logger.error(f"✗ Failed to connect to MongoDB: {e}")
        raise


async def close_mongodb_connection():
    """
    Close MongoDB connection

    Should be called on application shutdown
    """
    global _client

    if _client:
        _client.close()
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """
    Get MongoDB database instance

    Returns:
        AsyncIOMotorDatabase instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _database is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongodb() first.")
    return _database


def get_users_collection() -> AsyncIOMotorCollection:
    """
    Get users collection

    Returns:
        AsyncIOMotorCollection for users
    """
    db = get_database()
    return db[USERS_COLLECTION]


def get_conversations_collection() -> AsyncIOMotorCollection:
    """
    Get conversations collection

    Returns:
        AsyncIOMotorCollection for conversations
    """
    db = get_database()
    return db[CONVERSATIONS_COLLECTION]


# ============================================
# USER CRUD OPERATIONS
# ============================================

async def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new user in MongoDB

    Args:
        user_data: User document to insert

    Returns:
        Created user document

    Raises:
        DuplicateKeyError: If user with email already exists
    """
    try:
        collection = get_users_collection()
        result = await collection.insert_one(user_data)

        user_data["_id"] = result.inserted_id
        logger.info(f"Created user: {user_data.get('email')}")
        return user_data

    except DuplicateKeyError:
        logger.warning(f"User already exists: {user_data.get('email')}")
        raise ValueError(f"User with email {user_data.get('email')} already exists")


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get user by email

    Args:
        email: User email

    Returns:
        User document or None if not found
    """
    try:
        collection = get_users_collection()
        user = await collection.find_one({"email": email})
        return user

    except PyMongoError as e:
        logger.error(f"Error fetching user {email}: {e}")
        return None


async def update_user(email: str, update_data: Dict[str, Any]) -> bool:
    """
    Update user data

    Args:
        email: User email
        update_data: Fields to update

    Returns:
        True if updated, False otherwise
    """
    try:
        collection = get_users_collection()
        result = await collection.update_one(
            {"email": email},
            {"$set": update_data}
        )

        if result.modified_count > 0:
            logger.info(f"Updated user: {email}")
            return True
        return False

    except PyMongoError as e:
        logger.error(f"Error updating user {email}: {e}")
        return False


async def delete_user(email: str) -> bool:
    """
    Delete user

    Args:
        email: User email

    Returns:
        True if deleted, False otherwise
    """
    try:
        collection = get_users_collection()
        result = await collection.delete_one({"email": email})

        if result.deleted_count > 0:
            logger.info(f"Deleted user: {email}")
            return True
        return False

    except PyMongoError as e:
        logger.error(f"Error deleting user {email}: {e}")
        return False


async def get_all_users() -> list:
    """
    Get all users

    Returns:
        List of user documents
    """
    try:
        collection = get_users_collection()
        cursor = collection.find({})
        users = await cursor.to_list(length=1000)
        return users

    except PyMongoError as e:
        logger.error(f"Error fetching all users: {e}")
        return []


async def user_exists(email: str) -> bool:
    """
    Check if user exists

    Args:
        email: User email

    Returns:
        True if user exists, False otherwise
    """
    user = await get_user_by_email(email)
    return user is not None


# ============================================
# DATABASE HEALTH CHECK
# ============================================

async def check_database_health() -> Dict[str, Any]:
    """
    Check MongoDB connection health

    Returns:
        Health status information
    """
    try:
        db = get_database()
        await db.command('ping')

        users_count = await get_users_collection().count_documents({})

        return {
            "status": "healthy",
            "database": DATABASE_NAME,
            "users_count": users_count,
            "connected": True
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "connected": False
        }


# ============================================
# CONVERSATION CRUD OPERATIONS
# ============================================

async def create_conversation(conversation_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new conversation in MongoDB

    Args:
        conversation_data: Conversation document to insert

    Returns:
        Created conversation document
    """
    try:
        collection = get_conversations_collection()
        result = await collection.insert_one(conversation_data)

        conversation_data["_id"] = result.inserted_id
        logger.info(f"Created conversation: {conversation_data.get('conversation_id')} for {conversation_data.get('user_email')}")
        return conversation_data

    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise


async def get_conversation_by_id(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Get conversation by ID

    Args:
        conversation_id: Conversation ID

    Returns:
        Conversation document or None if not found
    """
    try:
        collection = get_conversations_collection()
        conversation = await collection.find_one({"conversation_id": conversation_id})
        return conversation

    except PyMongoError as e:
        logger.error(f"Error fetching conversation {conversation_id}: {e}")
        return None


async def get_user_conversations(user_email: str, limit: int = 4) -> list:
    """
    Get user's recent conversations (limited to last N conversations)

    Args:
        user_email: User email
        limit: Maximum number of conversations to return (default: 4)

    Returns:
        List of conversation documents, sorted by most recent first
    """
    try:
        collection = get_conversations_collection()
        cursor = collection.find({"user_email": user_email}).sort("updated_at", -1).limit(limit)
        conversations = await cursor.to_list(length=limit)
        return conversations

    except PyMongoError as e:
        logger.error(f"Error fetching conversations for {user_email}: {e}")
        return []


async def update_conversation(conversation_id: str, update_data: Dict[str, Any]) -> bool:
    """
    Update conversation data

    Args:
        conversation_id: Conversation ID
        update_data: Fields to update

    Returns:
        True if updated, False otherwise
    """
    try:
        collection = get_conversations_collection()
        result = await collection.update_one(
            {"conversation_id": conversation_id},
            {"$set": update_data}
        )

        if result.modified_count > 0:
            logger.info(f"Updated conversation: {conversation_id}")
            return True
        return False

    except PyMongoError as e:
        logger.error(f"Error updating conversation {conversation_id}: {e}")
        return False


async def delete_conversation(conversation_id: str) -> bool:
    """
    Delete conversation

    Args:
        conversation_id: Conversation ID

    Returns:
        True if deleted, False otherwise
    """
    try:
        collection = get_conversations_collection()
        result = await collection.delete_one({"conversation_id": conversation_id})

        if result.deleted_count > 0:
            logger.info(f"Deleted conversation: {conversation_id}")
            return True
        return False

    except PyMongoError as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        return False


async def delete_old_conversations(user_email: str, keep_count: int = 4) -> int:
    """
    Delete old conversations beyond the keep_count limit

    Args:
        user_email: User email
        keep_count: Number of recent conversations to keep (default: 4)

    Returns:
        Number of conversations deleted
    """
    try:
        collection = get_conversations_collection()

        # Find conversations to delete (oldest ones beyond keep_count)
        cursor = collection.find({"user_email": user_email}).sort("updated_at", -1).skip(keep_count)
        conversations_to_delete = await cursor.to_list(length=None)

        if not conversations_to_delete:
            return 0

        # Delete these conversations
        conversation_ids = [conv["conversation_id"] for conv in conversations_to_delete]
        result = await collection.delete_many({"conversation_id": {"$in": conversation_ids}})

        logger.info(f"Deleted {result.deleted_count} old conversations for {user_email}")
        return result.deleted_count

    except PyMongoError as e:
        logger.error(f"Error deleting old conversations for {user_email}: {e}")
        return 0
