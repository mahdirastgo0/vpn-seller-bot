import asyncio
from urllib.parse import quote

import httpx

from aiogram import F, Router
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud import (
    get_or_create_user,
    list_user_configs,
    get_user_config,
    update_vpn_config_link,
)
from app.services.sanaei_client import build_config_link
from app.utils import texts
from app.utils.qrcode_gen import generate_qr_bytes
from app.keyboards.user_kb import (
    config_kb,
    configs_global_kb,
)

router = Router(name="my_configs")


def bytes_to_gb(value: int | float | None) -> float:
    if not value:
        return 0.0

    return value / (1024 ** 3)


async def fetch_inbound(panel, inbound_id: int) -> dict | None:
    url = (
        panel.url
        + "/panel/api/inbounds/list"
    )

    async with httpx.AsyncClient(
        verify=False,
        timeout=20,
    ) as client:

        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {panel.api_token}",
            },
        )

        response.raise_for_status()

        data = response.json()

    if not data.get("success"):
        return None

    for inbound in data.get("obj", []):
        if int(inbound.get("id", 0)) == int(inbound_id):
            return inbound

    return None


async def refresh_config_from_panel(config):
    panel = settings.PANELS.get(config.panel_key)

    if not panel:
        raise RuntimeError("Panel not found")

    inbound = await fetch_inbound(
        panel,
        config.inbound_id,
    )

    if not inbound:
        raise RuntimeError("Inbound not found")

    # پیدا کردن کلاینت فعلی
    client_found = None

    for client in inbound.get("settings", {}).get("clients", []):
        if (
            client.get("id") == config.client_uuid
            or client.get("email") == config.client_email
        ):
            client_found = client
            break

    if client_found is None:
        # بعضی نسخه‌های Sanaei اطلاعات را در clientStats دارند
        for client in inbound.get("clientStats", []):
            if (
                client.get("id") == config.client_uuid
                or client.get("email") == config.client_email
            ):
                client_found = client
                break

    if client_found is None:
        raise RuntimeError("Client not found on panel")

    # ساخت لینک جدید بر اساس تنظیمات فعلی inbound
    new_link = build_config_link(
        panel,
        inbound,
        config.client_uuid,
        config.client_email,
    )

    # آمار مصرف
    used_bytes = 0
    total_bytes = config.traffic_gb * 1024 ** 3

    # اول clientStats
    for stat in inbound.get("clientStats", []):
        if (
            stat.get("id") == config.client_uuid
            or stat.get("email") == config.client_email
        ):
            used_bytes = (
                int(stat.get("up") or 0)
                + int(stat.get("down") or 0)
            )

            if stat.get("total"):
                total_bytes = int(stat.get("total"))

            break

    # سپس settings.clients اگر totalGB داشته باشد
    if client_found:
        total_gb = client_found.get("totalGB")

        if total_gb is not None:
            try:
                total_bytes = int(total_gb)
            except (ValueError, TypeError):
                pass

    return {
        "inbound": inbound,
        "link": new_link,
        "used_gb": bytes_to_gb(used_bytes),
        "total_gb": total_bytes / (1024 ** 3),
    }


def format_gb(value: float) -> str:
    if value < 0.01:
        return "0"

    if value >= 100:
        return f"{value:.0f}"

    return f"{value:.2f}".rstrip("0").rstrip(".")


def config_status(config) -> str:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    expire = config.expire_at

    if expire.tzinfo is None:
        expire = expire.replace(tzinfo=timezone.utc)

    if expire <= now:
        return "🔴 منقضی شده"

    return "🟢 فعال"


async def build_configs_message(
    session: AsyncSession,
    user_id: int,
) -> str:
    configs = await list_user_configs(
        session,
        user_id,
    )

    if not configs:
        return texts.MY_CONFIGS_EMPTY

    text = texts.MY_CONFIGS_HEADER

    for cfg in configs:
        panel = settings.PANELS.get(cfg.panel_key)

        panel_name = (
            panel.name
            if panel
            else cfg.panel_key
        )

        used = "0"
        total = str(cfg.traffic_gb)

        try:
            if panel:
                data = await refresh_config_from_panel(cfg)

                used = format_gb(data["used_gb"])
                total = format_gb(data["total_gb"])

        except Exception:
            pass

        expire = cfg.expire_at

        if expire.tzinfo is not None:
            expire_text = expire.strftime("%Y/%m/%d")
        else:
            expire_text = expire.strftime("%Y/%m/%d")

        text += texts.MY_CONFIGS_ITEM.format(
            panel_name=panel_name,
            config_id=cfg.id,
            used=used,
            traffic=total,
            expire_date=expire_text,
            status=config_status(cfg),
        )

        text += "\n\n"

    return text


@router.message(F.text == "📂 کانفیگ‌های من")
async def my_configs(
    message: Message,
    session: AsyncSession,
) -> None:

    user = await get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    configs = await list_user_configs(
        session,
        user.id,
    )

    if not configs:
        await message.answer(
            texts.MY_CONFIGS_EMPTY,
            parse_mode="HTML",
        )
        return

    for cfg in configs:
        panel = settings.PANELS.get(cfg.panel_key)

        panel_name = (
            panel.name
            if panel
            else cfg.panel_key
        )

        used = "0"
        total = str(cfg.traffic_gb)

        try:
            data = await refresh_config_from_panel(cfg)

            used = format_gb(data["used_gb"])
            total = format_gb(data["total_gb"])

            # اگر لینک تغییر کرده، دیتابیس هم آپدیت شود
            if data["link"] != cfg.config_link:
                await update_vpn_config_link(
                    session,
                    cfg,
                    data["link"],
                )

        except Exception:
            pass

        text = texts.MY_CONFIGS_ITEM.format(
            panel_name=panel_name,
            config_id=cfg.id,
            used=used,
            traffic=total,
            expire_date=cfg.expire_at.strftime("%Y/%m/%d"),
            status=config_status(cfg),
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=config_kb(cfg.id),
        )

    await message.answer(
        "برای دریافت لینک، QR یا بروزرسانی هر سرویس از دکمه‌های زیر آن استفاده کن.",
        reply_markup=configs_global_kb(),
    )


@router.callback_query(F.data.startswith("config_link:"))
async def config_link(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:

    config_id = int(callback.data.split(":")[1])

    user = await get_or_create_user(
        session,
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    cfg = await get_user_config(
        session,
        config_id,
        user.id,
    )

    if not cfg:
        await callback.answer(
            "این کانفیگ پیدا نشد.",
            show_alert=True,
        )
        return

    try:
        data = await refresh_config_from_panel(cfg)

        await update_vpn_config_link(
            session,
            cfg,
            data["link"],
        )

        await callback.message.answer(
            texts.CONFIG_LINK_TEXT.format(
                link=data["link"],
            ),
            parse_mode="HTML",
        )

        await callback.answer("لینک دریافت شد ✅")

    except Exception as exc:
        print(
            f"[CONFIG LINK ERROR] {exc}"
        )

        await callback.answer(
            "دریافت لینک انجام نشد.",
            show_alert=True,
        )


@router.callback_query(F.data.startswith("config_qr:"))
async def config_qr(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:

    config_id = int(callback.data.split(":")[1])

    user = await get_or_create_user(
        session,
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    cfg = await get_user_config(
        session,
        config_id,
        user.id,
    )

    if not cfg:
        await callback.answer(
            "این کانفیگ پیدا نشد.",
            show_alert=True,
        )
        return

    try:
        data = await refresh_config_from_panel(cfg)

        await update_vpn_config_link(
            session,
            cfg,
            data["link"],
        )

        qr = generate_qr_bytes(
            data["link"]
        )

        await callback.message.answer_photo(
            photo=BufferedInputFile(
                qr.read(),
                filename=f"config_{cfg.id}.png",
            ),
            caption=(
                f"📱 <b>QR Code سرویس #{cfg.id}</b>\n\n"
                "با اسکن این QR می‌تونی کانفیگ رو به کلاینت VPN اضافه کنی."
            ),
            parse_mode="HTML",
        )

        await callback.answer("QR آماده شد ✅")

    except Exception as exc:
        print(
            f"[CONFIG QR ERROR] {exc}"
        )

        await callback.answer(
            "ساخت QR انجام نشد.",
            show_alert=True,
        )


@router.callback_query(F.data.startswith("config_refresh:"))
async def config_refresh(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:

    config_id = int(
        callback.data.split(":")[1]
    )

    user = await get_or_create_user(
        session,
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    cfg = await get_user_config(
        session,
        config_id,
        user.id,
    )

    if not cfg:
        await callback.answer(
            "این کانفیگ پیدا نشد.",
            show_alert=True,
        )
        return

    try:
        data = await refresh_config_from_panel(
            cfg
        )

        await update_vpn_config_link(
            session,
            cfg,
            data["link"],
        )

        panel = settings.PANELS.get(
            cfg.panel_key
        )

        panel_name = (
            panel.name
            if panel
            else cfg.panel_key
        )

        text = texts.MY_CONFIGS_ITEM.format(
            panel_name=panel_name,
            config_id=cfg.id,
            used=format_gb(
                data["used_gb"]
            ),
            traffic=format_gb(
                data["total_gb"]
            ),
            expire_date=cfg.expire_at.strftime(
                "%Y/%m/%d"
            ),
            status=config_status(cfg),
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=config_kb(cfg.id),
        )

        await callback.answer(
            "کانفیگ بروزرسانی شد ✅"
        )

    except Exception as exc:
        print(
            f"[CONFIG REFRESH ERROR] {exc}"
        )

        await callback.answer(
            "❌ بروزرسانی انجام نشد.",
            show_alert=True,
        )


@router.callback_query(F.data == "configs_refresh_all")
async def configs_refresh_all(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:

    user = await get_or_create_user(
        session,
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    configs = await list_user_configs(
        session,
        user.id,
    )

    if not configs:
        await callback.answer(
            "کانفیگی نداری.",
            show_alert=True,
        )
        return

    success = 0

    for cfg in configs:
        try:
            data = await refresh_config_from_panel(
                cfg
            )

            await update_vpn_config_link(
                session,
                cfg,
                data["link"],
            )

            success += 1

        except Exception as exc:
            print(
                f"[REFRESH ALL] config={cfg.id} error={exc}"
            )

    await callback.answer(
        f"✅ {success} کانفیگ بروزرسانی شد.",
        show_alert=True,
    )

    try:
        await callback.message.edit_text(
            "🔄 <b>کانفیگ‌ها بروزرسانی شدند.</b>\n\n"
            "برای مشاهده اطلاعات جدید، دوباره «📂 کانفیگ‌های من» را بزن.",
            parse_mode="HTML",
            reply_markup=configs_global_kb(),
        )
    except Exception:
        pass