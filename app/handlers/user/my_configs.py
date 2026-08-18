from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud import get_or_create_user, list_user_configs
from app.utils import texts

router = Router(name="my_configs")


def format_expire_date(dt: datetime) -> str:
    if not dt:
        return "نامشخص"

    return dt.strftime("%Y/%m/%d")


def config_status(expire_at: datetime) -> tuple[str, str]:
    if not expire_at:
        return "⚪️ نامشخص", "unknown"

    now = datetime.now(timezone.utc)

    if expire_at.tzinfo is None:
        expire_at = expire_at.replace(tzinfo=timezone.utc)

    if expire_at <= now:
        return "🔴 منقضی شده", "expired"

    return "🟢 فعال", "active"


def config_keyboard(config_id: int):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 دریافت لینک",
                    callback_data=f"config_link:{config_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 بروزرسانی",
                    callback_data=f"config_refresh:{config_id}",
                ),
            ],
        ]
    )


def build_config_text(config, panel_name: str) -> str:
    status, _ = config_status(config.expire_at)

    return (
        f"📡 <b>سرویس VPN</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>سرویس #{config.id}</b>\n"
        f"🌍 <b>لوکیشن:</b> {panel_name}\n"
        f"📊 <b>حجم:</b> {config.traffic_gb} GB\n"
        f"📅 <b>انقضا:</b> {format_expire_date(config.expire_at)}\n"
        f"📌 <b>وضعیت:</b> {status}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )


async def show_configs(
    message: Message,
    session: AsyncSession,
) -> None:

    user = await get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    configs = await list_user_configs(session, user.id)

    if not configs:
        await message.answer(texts.MY_CONFIGS_EMPTY)
        return

    await message.answer(
        "📂 <b>کانفیگ‌های من</b>\n\n"
        "سرویس‌های خریداری‌شده شما در این بخش نمایش داده می‌شوند.",
        parse_mode="HTML",
    )

    for cfg in configs:

        panel = settings.PANELS.get(cfg.panel_key)

        panel_name = (
            panel.name
            if panel
            else cfg.panel_key
        )

        text = build_config_text(
            cfg,
            panel_name,
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=config_keyboard(cfg.id),
        )


@router.message(F.text == "📂 کانفیگ‌های من")
async def my_configs(
    message: Message,
    session: AsyncSession,
) -> None:

    await show_configs(
        message,
        session,
    )


@router.callback_query(F.data.startswith("config_link:"))
async def config_link(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:

    from sqlalchemy import select
    from app.database.models import VpnConfig

    config_id = int(
        callback.data.split(":", 1)[1]
    )

    result = await session.execute(
        select(VpnConfig).where(
            VpnConfig.id == config_id,
            VpnConfig.user_id.isnot(None),
        )
    )

    config = result.scalar_one_or_none()

    if config is None:
        await callback.answer(
            "❌ کانفیگ پیدا نشد.",
            show_alert=True,
        )
        return

    panel = settings.PANELS.get(config.panel_key)

    panel_name = (
        panel.name
        if panel
        else config.panel_key
    )

    status, _ = config_status(config.expire_at)

    text = (
        f"🔗 <b>لینک اتصال سرویس #{config.id}</b>\n\n"
        f"🌍 <b>لوکیشن:</b> {panel_name}\n"
        f"📌 <b>وضعیت:</b> {status}\n\n"
        f"<code>{config.config_link}</code>"
    )

    await callback.message.answer(
        text,
        parse_mode="HTML",
    )

    await callback.answer(
        "✅ لینک ارسال شد.",
    )


@router.callback_query(F.data.startswith("config_refresh:"))
async def config_refresh(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:

    from sqlalchemy import select
    from app.database.models import VpnConfig

    config_id = int(
        callback.data.split(":", 1)[1]
    )

    result = await session.execute(
        select(VpnConfig).where(
            VpnConfig.id == config_id,
        )
    )

    config = result.scalar_one_or_none()

    if config is None:
        await callback.answer(
            "❌ کانفیگ پیدا نشد.",
            show_alert=True,
        )
        return

    panel = settings.PANELS.get(config.panel_key)

    if panel is None:
        await callback.answer(
            "❌ پنل این سرویس پیدا نشد.",
            show_alert=True,
        )
        return

    # فعلاً اطلاعات ذخیره‌شده را دوباره نمایش می‌دهیم.
    # در مرحله بعد می‌توانیم این قسمت را مستقیماً
    # از API پنل بخوانیم و مصرف/انقضا را واقعی کنیم.

    status, _ = config_status(config.expire_at)

    text = (
        f"🔄 <b>اطلاعات سرویس بروزرسانی شد</b>\n\n"
        f"📡 <b>سرویس #{config.id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🌍 <b>لوکیشن:</b> {panel.name}\n"
        f"📊 <b>حجم:</b> {config.traffic_gb} GB\n"
        f"📅 <b>انقضا:</b> {format_expire_date(config.expire_at)}\n"
        f"📌 <b>وضعیت:</b> {status}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=config_keyboard(config.id),
    )

    await callback.answer(
        "✅ اطلاعات بروزرسانی شد.",
    )