from aiogram import Router, F, types
from aiogram.filters import Command
import time
from aiogram.utils.keyboard import InlineKeyboardBuilder
from user_manager import get_user_data, update_user_balance, add_item_to_inventory, update_user_field
from escape import escape_html

router = Router()

ITEMS = {
    # БИЗНЕСЫ (Окупаемость - 10 сборов)
    "шаурма": {"name": "🏪 Ларёк с шаурмой", "price": 100000, "cat": "biz", "action": "business", "income": 10000},
    "мойка": {"name": "🚿 Автомойка", "price": 500000, "cat": "biz", "action": "business", "income": 50000},
    "вендинг": {"name": "🍬 Вендинг", "price": 800000, "cat": "biz", "action": "business", "income": 80000},
    "кофейня": {"name": "☕️ Кофейня", "price": 1500000, "cat": "biz", "action": "business", "income": 150000},
    "ресторан": {"name": "🍽 Ресторан", "price": 3000000, "cat": "biz", "action": "business", "income": 300000},
    "отель": {"name": "🏨 Отель", "price": 7000000, "cat": "biz", "action": "business", "income": 700000},
    "ферма": {"name": "🌽 Ферма", "price": 12000000, "cat": "biz", "action": "business", "income": 1200000},
    "завод": {"name": "🏭 Завод", "price": 25000000, "cat": "biz", "action": "business", "income": 2500000},
    "салон": {"name": "🚙 Автосалон", "price": 50000000, "cat": "biz", "action": "business", "income": 5000000},
    "нефть": {"name": "🛢 Вышка", "price": 100000000, "cat": "biz", "action": "business", "income": 10000000},
    "банк": {"name": "🏦 Банк", "price": 250000000, "cat": "biz", "action": "business", "income": 25000000},
    "айти": {"name": "💻 IT-компания", "price": 500000000, "cat": "biz", "action": "business", "income": 50000000},
    "казино": {"name": "🎰 Казино", "price": 1000000000, "cat": "biz", "action": "business", "income": 100000000},
    "космодром": {"name": "🚀 Космодром", "price": 5000000000, "cat": "biz", "action": "business", "income": 500000000},
    "планета": {"name": "🪐 Колония", "price": 10000000000, "cat": "biz", "action": "business", "income": 1000000000},
    
    # МАШИНЫ
    "лада": {"name": "🚗 Lada Priora", "price": 50000, "cat": "cars", "action": "car", "income": 2000},
    "камри": {"name": "🚙 Toyota Camry", "price": 150000, "cat": "cars", "action": "car", "income": 7000},
    "бмв": {"name": "🚕 BMW M5", "price": 500000, "cat": "cars", "action": "car", "income": 20000},
    "гелик": {"name": "⬛️ Geländewagen", "price": 1200000, "cat": "cars", "action": "car", "income": 50000},
    "бугатти": {"name": "🏎 Bugatti Chiron", "price": 5000000, "cat": "cars", "action": "car", "income": 200000},
    "самолет": {"name": "🛩 Частный Jet", "price": 50000000, "cat": "cars", "action": "car", "income": 2500000},
    
    # ПРОЧЕЕ
    "вип": {"name": "💎 Статус VIP", "price": 1000000, "cat": "other", "action": "other"},
    "антиварн": {"name": "💊 Снять варн", "price": 250000, "cat": "other", "action": "other"}
}

def get_main_shop_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏢 Бизнесы", callback_data="shop_cat_biz")
    builder.button(text="🚗 Машины", callback_data="shop_cat_cars")
    builder.button(text="💎 Прочее", callback_data="shop_cat_other")
    builder.adjust(2)
    return builder.as_markup()

def get_category_kb(category):
    builder = InlineKeyboardBuilder()
    for item_id, info in ITEMS.items():
        if info.get('cat') == category:
            builder.button(text=f"{info['name']} - {info['price']} сыр.", callback_data=f"buy_{item_id}")
    builder.button(text="⬅️ Назад", callback_data="shop_main")
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("shop"))
async def cmd_shop(message: types.Message):
    data = await get_user_data(message.chat.id, message.from_user.id)

    debts = data.get('debts', {})

    current_time = time.time()
    has_overdue_debt = False

    for k, v in debts.items():
        if k.startswith("bank_") and v > 0:
            parts = k.split("_")
            if len(parts) >= 3:
                due_date = int(parts[2])
                if current_time > due_date:
                    has_overdue_debt = True
                    break

    if has_overdue_debt:
        return await message.answer("❌ На вас наложен арест! У вас есть просроченный долг перед банком. Покупки запрещены.")

    if data.get('is_banned'): return
    
    text = (
        f"🛒 <b>МАГАЗИН СЫРОЕДА</b>\n\n"
        f"Твой баланс: <b>{data.get('balance', 0)}</b> сыр.\n"
        f"Выбери категорию товаров ниже:"
    )
    await message.answer(text, reply_markup=get_main_shop_kb())

@router.callback_query(F.data == "shop_main")
async def shop_back(callback: types.CallbackQuery):
    data = await get_user_data(callback.message.chat.id, callback.from_user.id)
    text = (f"🛒 <b>МАГАЗИН СЫРОЕДА</b>\n\n"
            f"Твой баланс: <b>{data.get('balance', 0)}</b> сыр.\n"
            f"Выбери категорию:")
    await callback.message.edit_text(text, reply_markup=get_main_shop_kb())

@router.callback_query(F.data.startswith("shop_cat_"))
async def show_category(callback: types.CallbackQuery):
    category = callback.data.replace("shop_cat_", "")
    cats_names = {"biz": "Бизнесы", "cars": "Машины", "other": "Разное"}
    
    text = f"📂 <b>Категория: {cats_names.get(category)}</b>\n\nВыбери товар для покупки:"
    await callback.message.edit_text(text, reply_markup=get_category_kb(category))

@router.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    item_id = callback.data.replace("buy_", "")
    item = ITEMS.get(item_id)
    if not item: return

    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await get_user_data(chat_id, user_id)

    if data.get('balance', 0) < item['price']:
        return await callback.answer("Недостаточно денег!", show_alert=True)

    if item.get('cat') == "biz":
        limit = 4 if data.get('is_vip') else 2
        inv = data.get('inventory', {})
        biz_count = sum(1 for k in inv if ITEMS.get(k, {}).get('cat') == 'biz')
        
        if item_id in inv:
            return await callback.answer("У тебя уже есть этот бизнес!", show_alert=True)
        if biz_count >= limit:
            return await callback.answer(f"Лимит бизнесов ({limit}) достигнут!", show_alert=True)

    await update_user_balance(chat_id, user_id, -item['price'])
    
    if item_id == "вип":
        await update_user_field(chat_id, user_id, 'is_vip', True)
    else:
        await add_item_to_inventory(chat_id, user_id, item_id)

    await callback.answer(f"Куплено: {item['name']}!", show_alert=True)
    await show_category(callback)