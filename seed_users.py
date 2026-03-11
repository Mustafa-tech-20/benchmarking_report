"""
Seed Initial Users to MongoDB
Run this script to populate the database with users
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from auth.database import connect_to_mongodb, create_user, user_exists, close_mongodb_connection, get_users_collection
from auth.jwt_handler import get_password_hash
from auth.models import UserRole

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def clear_all_users():
    """Delete all existing users from MongoDB"""
    collection = get_users_collection()
    result = await collection.delete_many({})
    logger.info(f"Deleted {result.deleted_count} existing users")


async def seed_users():
    """Create users in MongoDB"""

    # Connect to MongoDB
    await connect_to_mongodb()

    # Clear all existing users first
    await clear_all_users()

    # Get passwords from environment variables (secure)
    vb_password = os.environ.get("VB_USER_PASSWORD")
    pp_password = os.environ.get("PP_USER_PASSWORD")
    vd_password = os.environ.get("VD_USER_PASSWORD")

    if not all([vb_password, pp_password, vd_password]):
        logger.error("Missing required environment variables:")
        logger.error("  VB_USER_PASSWORD, PP_USER_PASSWORD, VD_USER_PASSWORD")
        logger.error("Please set these environment variables before running this script.")
        await close_mongodb_connection()
        return

    # Users with passwords from environment
    users = [
        {
            "email": os.environ.get("VB_USER_EMAIL", "benchmarking@mahindra.com"),
            "hashed_password": get_password_hash(vb_password),
            "role": UserRole.VB.value,
            "full_name": "Vehicle Benchmarking Team",
            "is_active": True,
        },
        {
            "email": os.environ.get("PP_USER_EMAIL", "planning@mahindra.com"),
            "hashed_password": get_password_hash(pp_password),
            "role": UserRole.PP.value,
            "full_name": "Product Planning Team",
            "is_active": True,
        },
        {
            "email": os.environ.get("VD_USER_EMAIL", "development@mahindra.com"),
            "hashed_password": get_password_hash(vd_password),
            "role": UserRole.VD.value,
            "full_name": "Vehicle Development Team",
            "is_active": True,
        },
    ]

    logger.info("=" * 60)
    logger.info("SEEDING USERS TO MONGODB")
    logger.info("=" * 60)

    created_count = 0

    for user_data in users:
        email = user_data["email"]
        try:
            await create_user(user_data)
            logger.info(f"Created user: {email} | Role: {user_data['role']}")
            created_count += 1
        except Exception as e:
            logger.error(f"Failed to create user {email}: {e}")

    logger.info("=" * 60)
    logger.info(f"SEEDING COMPLETE - Created {created_count} users")
    logger.info("=" * 60)

    await close_mongodb_connection()


if __name__ == "__main__":
    asyncio.run(seed_users())
