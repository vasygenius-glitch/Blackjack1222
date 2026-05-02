import time
import secrets
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from db import get_db
from escape import escape_html
from user_manager import get_user_data, update_user_balance, update_user_field

router = Router()

PETS_SHOP = {
    "cat": {"name": "🐱 Кот", "price": 1000000, "bonus": "Дает +20% к заработку на /work"},
    "dog": {"name": "🐶 Собака", "price": 2000000, "bonus": "Снижает глобальный налог на 5%"},
    "dragon": {"name": "🐉 Дракон", "price": 50000000, "bonus": "Дает +10% к победе в /crime и защищает от коллекторов!"}
}

@router.message(Command("pets"))
async def cmd_pets(message: types.Message):
    text = "🐾 <b>Зоомагазин Питомцев:</b>\n\n"
    for pet_id, info in PETS_SHOP.items():
        text += f"{info['name']} — {info['price']} сыр.\n<i>{info['bonus']}</i>\nКупить: <code>/buypet {pet_id}</code>\n\n"
    text += "⚠️ Питомца нужно кормить раз в день командой <code>/feed</code>, иначе он сбежит!"
    await message.answer(text)

@router.message(Command("buypet"))
async def cmd_buypet(message: types.Message):
    args = message.text.split()
    if len(args) < 2: return await message.answer("Укажите ID питомца.")

    pet_id = args[1].lower()
    if pet_id not in PETS_SHOP: return await message.answer("Такого питомца нет в магазине.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    data = await get_user_data(chat_id, user_id)

    if data.get('pet'): return await message.answer("У вас уже есть питомец! Чтобы купить нового, старый должен сбежать.")

    price = PETS_SHOP[pet_id]['price']
    if data.get('balance', 0) < price: return await message.answer(f"Недостаточно средств. Нужно {price} сыроежек.")

    await update_user_balance(chat_id, user_id, -price)

    pet_data = {
        'id': pet_id,
        'last_fed': int(time.time())
    }
    await update_user_field(chat_id, user_id, 'pet', pet_data)
    await message.answer(f"🎉 Вы успешно купили питомца: <b>{PETS_SHOP[pet_id]['name']}</b>!\nНе забывайте кормить его командой <code>/feed</code>!")

@router.message(Command("feed"))
async def cmd_feed(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    data = await get_user_data(chat_id, user_id)

    pet = data.get('pet')
    if not pet: return await message.answer("У вас нет питомца.")

    current_time = int(time.time())
    last_fed = pet.get('last_fed', 0)

    if current_time - last_fed > 86400 * 2: # 2 дня
        await update_user_field(chat_id, user_id, 'pet', None)
        return await message.answer("😢 Ваш питомец так долго голодал, что сбежал от вас...")

    if current_time - last_fed < 3600 * 12: # 12 часов
        return await message.answer("Ваш питомец еще не проголодался.")

    food_price = 5000
    if data.get('balance', 0) < food_price: return await message.answer(f"Еда для питомца стоит {food_price} сыроежек. У вас нет денег!")

    await update_user_balance(chat_id, user_id, -food_price)
    pet['last_fed'] = current_time
    await update_user_field(chat_id, user_id, 'pet', pet)
    await message.answer("🍗 Вы покормили своего питомца! Он счастлив и готов приносить бонусы.")
