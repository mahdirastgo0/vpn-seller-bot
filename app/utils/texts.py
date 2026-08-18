from pathlib import Path
WELCOME = (
    "👋 سلام {name} عزیز، به ربات فروش کانفیگ VPN خوش اومدی!\n\n"
    "از منوی زیر می‌تونی یه سرویس بخری، کانفیگ‌های فعالت رو ببینی یا با پشتیبانی در ارتباط باشی."
)

CHOOSE_PANEL = "🌍 یکی از لوکیشن‌های زیر رو انتخاب کن:"
CHOOSE_PLAN = "📦 یکی از پلن‌های زیر رو انتخاب کن:"
CHOOSE_PAYMENT = "💳 روش پرداخت رو انتخاب کن:"

NO_PLANS = "در حال حاضر پلن فعالی برای این لوکیشن ثبت نشده. بعداً دوباره امتحان کن."

ORDER_SUMMARY = (
    "🧾 خلاصه سفارش:\n"
    "▫️ لوکیشن: {panel_name}\n"
    "▫️ پلن: {plan_name}\n"
    "▫️ مدت: {duration} روز\n"
    "▫️ حجم: {traffic} گیگابایت\n"
    "▫️ مبلغ: {amount:,} {currency}\n"
)

ZARINPAL_LINK = "برای پرداخت روی دکمه زیر بزن. بعد از پرداخت موفق، کانفیگ به‌صورت خودکار برات ارسال میشه ✅"

CARD_INFO = (
    "💳 لطفاً مبلغ {amount:,} {currency} رو به شماره کارت زیر واریز کن:\n\n"
    "`{card_number}`\n"
    "به نام: {holder}\n"
    "بانک: {bank}\n\n"
    "بعد از واریز، عکس رسید رو همینجا برام بفرست."
)

CARD_RECEIPT_RECEIVED = (
    "✅ رسیدت دریافت شد و برای بررسی به ادمین ارسال شد.\n"
    "به محض تایید، کانفیگت برات ارسال میشه. لطفاً کمی صبر کن 🙏"
)

CRYPTO_CHOOSE_COIN = "🪙 ارز مورد نظر برای پرداخت رو انتخاب کن:"
CRYPTO_INFO = (
    "🪙 لطفاً معادل {amount:,} {currency} رو به آدرس زیر ({coin}) واریز کن:\n\n"
    "`{address}`\n\n"
    "بعد از واریز، هش تراکنش (TxID) رو همینجا برام بفرست."
)
CRYPTO_TX_RECEIVED = (
    "✅ هش تراکنش دریافت شد و برای بررسی به ادمین ارسال شد.\n"
    "به محض تایید، کانفیگت برات ارسال میشه. لطفاً کمی صبر کن 🙏"
)

ORDER_APPROVED_USER = "🎉 پرداختت تایید شد! کانفیگ VPN تو آماده‌ست:"
ORDER_REJECTED_USER = "❌ متاسفانه سفارشت (#{order_id}) توسط ادمین رد شد. برای پیگیری با پشتیبانی در تماس باش: {support}"

ADMIN_NEW_CARD_ORDER = (
    "🆕 سفارش کارت‌به‌کارت جدید #{order_id}\n"
    "کاربر: {user_mention} (ID: {telegram_id})\n"
    "پلن: {plan_name} — {amount:,} {currency}\n"
)
ADMIN_NEW_CRYPTO_ORDER = (
    "🆕 سفارش رمزارزی جدید #{order_id}\n"
    "کاربر: {user_mention} (ID: {telegram_id})\n"
    "پلن: {plan_name} — {amount:,} {currency}\n"
    "ارز: {coin}\n"
    "TxID: `{tx_id}`\n"
)

NOT_ADMIN = "⛔️ این دستور فقط برای ادمین‌هاست."
NO_PENDING_ORDERS = "در حال حاضر سفارش در انتظاری وجود نداره."

MY_CONFIGS_EMPTY = p = Path("~/vpn-seller-bot/app/utils/texts.py").expanduser()
text = p.read_text()

text = text.replace(
    'MY_CONFIGS_EMPTY = "هنوز هیچ کانفیگ فعالی نداری. از منوی «خرید سرویس» شروع کن 🛒"',
    'MY_CONFIGS_EMPTY = "📂 <b>کانفیگ‌های من</b>\\n\\nهنوز هیچ سرویس فعالی نداری.\\n\\n🛒 از منوی «خرید سرویس» می‌تونی اولین سرویس خودت رو تهیه کنی."'
)

p.write_text(text)
print("✅ empty config text updated")

p = Path("~/vpn-seller-bot/app/utils/texts.py").expanduser()
text = p.read_text()

old = '''MY_CONFIGS_ITEM = (
    "🔹 {panel_name} | {traffic} گیگ | انقضا: {expire_date}\\n"
    "`{link}`\\n"
)
'''

new = '''MY_CONFIGS_ITEM = (
    "📡 <b>سرویس VPN</b>\\n"
    "━━━━━━━━━━━━━━━━━━\\n"
    "🌍 <b>لوکیشن:</b> {panel_name}\\n"
    "📊 <b>حجم:</b> {traffic} GB\\n"
    "📅 <b>انقضا:</b> {expire_date}\\n"
    "━━━━━━━━━━━━━━━━━━"
)
'''

if old in text:
    text = text.replace(old, new)

p.write_text(text)
print("✅ texts.py updated")

SUPPORT_TEXT = "برای ارتباط با پشتیبانی به آیدی زیر پیام بده:\n{support}"
