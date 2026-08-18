from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Order, OrderStatus, Plan, PaymentMethod, User, VpnConfig


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None, full_name: str | None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username, full_name=full_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def list_active_plans(session: AsyncSession, panel_key: str | None = None) -> list[Plan]:
    query = select(Plan).where(Plan.is_active.is_(True))
    if panel_key:
        query = query.where(Plan.panel_key == panel_key)
    result = await session.execute(query.order_by(Plan.price))
    return list(result.scalars().all())


async def get_plan(session: AsyncSession, plan_id: int) -> Plan | None:
    return await session.get(Plan, plan_id)


async def create_order(
    session: AsyncSession,
    user: User,
    plan: Plan,
    payment_method: PaymentMethod,
) -> Order:
    order = Order(
        user_id=user.id,
        plan_id=plan.id,
        amount=plan.price,
        payment_method=payment_method,
        status=OrderStatus.PENDING,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.plan))
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def get_order_by_authority(session: AsyncSession, authority: str) -> Order | None:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.plan))
        .where(Order.zarinpal_authority == authority)
    )
    return result.scalar_one_or_none()


async def mark_order_paid(session: AsyncSession, order: Order, admin_id: int | None = None) -> None:
    order.status = OrderStatus.PAID
    order.reviewed_by_admin_id = admin_id
    await session.commit()


async def mark_order_rejected(session: AsyncSession, order: Order, admin_id: int | None = None) -> None:
    order.status = OrderStatus.REJECTED
    order.reviewed_by_admin_id = admin_id
    await session.commit()


async def save_vpn_config(
    session: AsyncSession,
    order: Order,
    panel_key: str,
    inbound_id: int,
    client_email: str,
    client_uuid: str,
    config_link: str,
    traffic_gb: int,
    duration_days: int,
) -> VpnConfig:
    cfg = VpnConfig(
        order_id=order.id,
        user_id=order.user_id,
        panel_key=panel_key,
        inbound_id=inbound_id,
        client_email=client_email,
        client_uuid=client_uuid,
        config_link=config_link,
        traffic_gb=traffic_gb,
        expire_at=datetime.utcnow() + timedelta(days=duration_days),
    )
    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)
    return cfg


async def list_user_configs(session: AsyncSession, user_id: int) -> list[VpnConfig]:
    result = await session.execute(
        select(VpnConfig).where(VpnConfig.user_id == user_id).order_by(VpnConfig.created_at.desc())
    )
    return list(result.scalars().all())


async def list_pending_orders(session: AsyncSession, method: PaymentMethod | None = None) -> list[Order]:
    query = (
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.plan))
        .where(Order.status == OrderStatus.PENDING)
    )
    if method:
        query = query.where(Order.payment_method == method)
    result = await session.execute(query.order_by(Order.created_at))
    return list(result.scalars().all())
