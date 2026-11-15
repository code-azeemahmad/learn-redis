import asyncio
import logging
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger(__name__)

SAMPLE_USERS = [
    # Tenant: company-a
    {
        "tenant_id": "company-a",
        "username": "charlie",
        "email": "charlie@companya.com",
        "full_name": "Charlie Davis"
    },
    {
        "tenant_id": "company-a",
        "username": "david",
        "email": "david@companya.com",
        "full_name": "David Miller"
    },
    {
        "tenant_id": "company-a",
        "username": "emma",
        "email": "emma@companya.com",
        "full_name": "Emma Watson"
    },
    # Tenant: company-b
    {
        "tenant_id": "company-b",
        "username": "sophia",
        "email": "sophia@companyb.com",
        "full_name": "Sophia Taylor"
    },
    {
        "tenant_id": "company-b",
        "username": "liam",
        "email": "liam@companyb.com",
        "full_name": "Liam Wilson"
    },
    {
        "tenant_id": "company-b",
        "username": "olivia",
        "email": "olivia@companyb.com",
        "full_name": "Olivia Brown"
    },
    # Tenant: acme-corp
    {
        "tenant_id": "acme-corp",
        "username": "wile",
        "email": "wile@acme.com",
        "full_name": "Wile E. Coyote"
    },
    {
        "tenant_id": "acme-corp",
        "username": "roadrunner",
        "email": "roadrunner@acme.com",
        "full_name": "Road Runner"
    },
    {
        "tenant_id": "acme-corp",
        "username": "bugs",
        "email": "bugs@acme.com",
        "full_name": "Bugs Bunny"
    },
    # Tenant: stark-industries
    {
        "tenant_id": "stark-industries",
        "username": "tony",
        "email": "tony@starkindustries.com",
        "full_name": "Tony Stark"
    },
    {
        "tenant_id": "stark-industries",
        "username": "pepper",
        "email": "pepper@starkindustries.com",
        "full_name": "Pepper Potts"
    },
    {
        "tenant_id": "stark-industries",
        "username": "rhodey",
        "email": "rhodey@starkindustries.com",
        "full_name": "James Rhodes"
    },
    {
        "tenant_id": "stark-industries",
        "username": "peter",
        "email": "peter@starkindustries.com",
        "full_name": "Peter Parker"
    },
]


async def seed_users():
    async with AsyncSessionLocal() as session:
        inserted_count = 0
        for data in SAMPLE_USERS:
            # Check if user already exists in this tenant
            result = await session.execute(
                select(User).where(
                    User.tenant_id == data["tenant_id"],
                    User.username == data["username"]
                )
            )
            existing_user = result.scalar_one_or_none()
            if not existing_user:
                new_user = User(
                    tenant_id=data["tenant_id"],
                    username=data["username"],
                    email=data["email"],
                    full_name=data["full_name"]
                )
                session.add(new_user)
                inserted_count += 1
                logger.info(f"Adding user '{data['username']}' for tenant '{data['tenant_id']}'")
            else:
                logger.info(f"User '{data['username']}' already exists in tenant '{data['tenant_id']}'. Skipping.")

        await session.commit()
        logger.info(f"Successfully seeded {inserted_count} sample users!")


if __name__ == "__main__":
    asyncio.run(seed_users())
