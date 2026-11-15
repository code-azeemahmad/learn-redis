import asyncio
from datetime import datetime, timezone, timedelta
import random
from app.database import AsyncSessionLocal
from app.models import Order
from sqlalchemy import func, select


async def seed_orders():
    async with AsyncSessionLocal() as session:
        # Check if orders already exist
        res = await session.execute(select(func.count(Order.id)))
        count = res.scalar_one()
        if count > 0:
            print(f"Orders already seeded ({count} orders). Skipping.")
            return

        orders = []
        base_date = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Company-A: 50 orders in November 2026
        for i in range(50):
            order_time = base_date + timedelta(days=random.randint(0, 28), hours=random.randint(0, 23), minutes=random.randint(0, 59))
            amount = round(random.uniform(50.0, 1500.0), 2)
            orders.append(Order(
                tenant_id="company-a",
                total_amount=amount,
                status="completed",
                created_at=order_time
            ))

        # Company-B: 30 orders in November 2026
        for i in range(30):
            order_time = base_date + timedelta(days=random.randint(0, 28), hours=random.randint(0, 23), minutes=random.randint(0, 59))
            amount = round(random.uniform(100.0, 2500.0), 2)
            orders.append(Order(
                tenant_id="company-b",
                total_amount=amount,
                status="completed",
                created_at=order_time
            ))

        # Stark Industries: 100 high-value orders in November 2026
        for i in range(100):
            order_time = base_date + timedelta(days=random.randint(0, 28), hours=random.randint(0, 23), minutes=random.randint(0, 59))
            amount = round(random.uniform(1000.0, 50000.0), 2)
            orders.append(Order(
                tenant_id="stark-industries",
                total_amount=amount,
                status="completed",
                created_at=order_time
            ))

        session.add_all(orders)
        await session.commit()
        print(f"Successfully seeded {len(orders)} orders across tenants!")


if __name__ == "__main__":
    asyncio.run(seed_orders())
