from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud import get_or_create_user, list_user_configs
from app.utils import texts

router = Router(name="my_configs")


@router.message(F.text == "📂 کانفیگ‌های من")
async def my_configs(message: Message, session: AsyncSession) -> None:
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

    text = "📂 کانفیگ‌های فعال تو:\n\n"
    for cfg in configs:
        panel_name = settings.PANELS.get(cfg.panel_key)
        text += texts.MY_CONFIGS_ITEM.format(
            panel_name=panel_name.name if panel_name else cfg.panel_key,
            traffic=cfg.traffic_gb,
            expire_date=cfg.expire_at.strftime("%Y-%m-%d"),
            link=cfg.config_link,
        )
        text += "\n"
    await message.answer(text, parse_mode="Markdown")
