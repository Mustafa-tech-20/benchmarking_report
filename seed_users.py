"""
Seed Initial Users to MongoDB
Run this script to populate the database with test users
"""

import asyncio
import logging
from dotenv import load_dotenv
from auth.database import connect_to_mongodb, create_user, user_exists, close_mongodb_connection
from auth.jwt_handler import get_password_hash
from auth.models import UserRole

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_users():
    """Create test users in MongoDB"""

    # Connect to MongoDB
    await connect_to_mongodb()

    # Test users
    test_users = [
        {
            "email": "vb@mahindra.com",
            "hashed_password": get_password_hash("vb123"),
            "role": UserRole.VB.value,
            "full_name": "Vehicle Benchmarking Team",
            "is_active": True,
        },
        {
            "email": "pp@mahindra.com",
            "hashed_password": get_password_hash("pp123"),
            "role": UserRole.PP.value,
            "full_name": "Product Planning Team",
            "is_active": True,
        },
        {
            "email": "vd@mahindra.com",
            "hashed_password": get_password_hash("vd123"),
            "role": UserRole.VD.value,
            "full_name": "Vehicle Development Team",
            "is_active": True,
        },
    ]

    logger.info("=" * 60)
    logger.info("SEEDING TEST USERS TO MONGODB")
    logger.info("=" * 60)

    created_count = 0
    skipped_count = 0

    for user_data in test_users:
        email = user_data["email"]

        # Check if user already exists
        if await user_exists(email):
            logger.warning(f"⊘ User already exists: {email}")
            skipped_count += 1
            continue

        # Create user
        try:
            await create_user(user_data)
            logger.info(f"✓ Created user: {email} | Role: {user_data['role']}")
            created_count += 1
        except Exception as e:
            logger.error(f"✗ Failed to create user {email}: {e}")

    logger.info("=" * 60)
    logger.info(f"SEEDING COMPLETE")
    logger.info(f"Created: {created_count} users")
    logger.info(f"Skipped: {skipped_count} users (already exist)")
    logger.info("=" * 60)

    # Display test credentials
    logger.info("\n🔐 TEST CREDENTIALS:")
    logger.info("-" * 60)
    logger.info("VB Role (Benchmarking):")
    logger.info("  Email: vb@mahindra.com")
    logger.info("  Password: vb123")
    logger.info("-" * 60)
    logger.info("PP Role (Product Planning):")
    logger.info("  Email: pp@mahindra.com")
    logger.info("  Password: pp123")
    logger.info("-" * 60)
    logger.info("VD Role (Vehicle Development):")
    logger.info("  Email: vd@mahindra.com")
    logger.info("  Password: vd123")
    logger.info("-" * 60)

    await close_mongodb_connection()


if __name__ == "__main__":
    asyncio.run(seed_users())
