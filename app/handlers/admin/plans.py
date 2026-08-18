from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud import list_active_plans
from app.database.models import Plan
from app.middlewares.admin_filter import IsAdmin
from app.states.user_states import AdminPlanFlow

router = Router(name="admin_plans")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _panels_choice_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=p.name, callback_data=f"admin_panel_choice:{key}")]
        for key, p in settings.PANELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("addplan"))
async def add_plan_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminPlanFlow.waiting_panel)
    await message.answer("پلن برای کدوم پنل باشه؟", reply_markup=_panels_choice_kb())


@router.callback_query(AdminPlanFlow.waiting_panel, F.data.startswith("admin_panel_choice:"))
async def add_plan_panel(callback: CallbackQuery, state: FSMContext) -> None:
    panel_key = callback.data.split(":", 1)[1]
    await state.update_data(panel_key=panel_key)
    await state.set_state(AdminPlanFlow.waiting_name)
    await callback.message.answer("نام پلن رو بفرست (مثلاً «۱ ماهه ۵۰ گیگ»):")
    await callback.answer()


@router.message(AdminPlanFlow.waiting_name, F.text)
async def add_plan_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminPlanFlow.waiting_duration)
    await message.answer("مدت اعتبار پلن به روز چند باشه؟ (فقط عدد)")


@router.message(AdminPlanFlow.waiting_duration, F.text)
async def add_plan_duration(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد بفرست.")
        return
    await state.update_data(duration_days=int(message.text.strip()))
    await state.set_state(AdminPlanFlow.waiting_traffic)
    await message.answer("حجم پلن به گیگابایت چند باشه؟ (فقط عدد، ۰ برای نامحدود)")


@router.message(AdminPlanFlow.waiting_traffic, F.text)
async def add_plan_traffic(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد بفرست.")
        return
    await state.update_data(traffic_gb=int(message.text.strip()))
    await state.set_state(AdminPlanFlow.waiting_price)
    await message.answer(f"قیمت پلن به {settings.CURRENCY_LABEL} چند باشه؟ (فقط عدد)")


@router.message(AdminPlanFlow.waiting_price, F.text)
async def add_plan_price(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text.strip().isdigit():
        await message.answer("لطفاً فقط عدد بفرست.")
        return

    data = await state.get_data()
    plan = Plan(
        panel_key=data["panel_key"],
        name=data["name"],
        duration_days=data["duration_days"],
        traffic_gb=data["traffic_gb"],
        price=int(message.text.strip()),
        is_active=True,
    )
    session.add(plan)
    await session.commit()
    await state.clear()

    await message.answer(f"✅ پلن «{plan.name}» با موفقیت اضافه شد.")


@router.message(Command("plans"))
async def list_plans(message: Message, session: AsyncSession) -> None:
    plans = await list_active_plans(session)
    if not plans:
        await message.answer("هیچ پلنی ثبت نشده.")
        return
    text = "📋 لیست پلن‌های فعال:\n\n"
    for p in plans:
        panel = settings.PANELS.get(p.panel_key)
        text += (
            f"#{p.id} | {panel.name if panel else p.panel_key} | {p.name} | "
            f"{p.duration_days} روز | {p.traffic_gb} گیگ | {p.price:,} {settings.CURRENCY_LABEL}\n"
        )
    await message.answer(text)


@router.message(Command("delplan"))
async def del_plan(message: Message, session: AsyncSession) -> None:
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("استفاده: /delplan <شماره پلن>")
        return
    plan = await session.get(Plan, int(parts[1]))
    if plan is None:
        await message.answer("پلن پیدا نشد.")
        return
    plan.is_active = False
    await session.commit()
    await message.answer(f"پلن #{plan.id} غیرفعال شد.")
