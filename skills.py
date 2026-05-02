from aiogram import Router, types
from aiogram.filters import Command
from user_manager import get_user_data, update_user_balance, update_user_field
from escape import escape_html

router = Router()

SKILLS = {
    "luck": {"name": "🍀 Удача", "desc": "Увеличивает шансы в казино", "base_price": 50000},
    "stealth": {"name": "🥷 Скрытность", "desc": "Меньше шанс нарваться на полицию в /crime", "base_price": 100000},
    "negotiation": {"name": "💼 Бизнесмен", "desc": "Снижает налоги при сборе бонуса", "base_price": 200000}
}

@router.message(Command("skills"))
async def cmd_skills(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, user_id, full_name)
    skills = data.get('skills', {})

    args = message.text.split()
    if len(args) == 1:
        text = "🎯 <b>Ваши навыки:</b>\n\n"
        for sk_id, sk_info in SKILLS.items():
            level = skills.get(sk_id, 0)
            price = sk_info['base_price'] * (level + 1)
            text += f"{sk_info['name']} (Уровень {level}/5)\n"
            text += f"<i>{sk_info['desc']}</i>\n"
            if level < 5:
                text += f"Улучшить: <code>/skills {sk_id}</code> за {price} сыроежек\n\n"
            else:
                text += "<i>Максимальный уровень!</i>\n\n"
        await message.answer(text)
        return

    sk_id = args[1]
    if sk_id not in SKILLS:
        await message.answer("Такого навыка нет. Введите `/skills` для списка.")
        return

    level = skills.get(sk_id, 0)
    if level >= 5:
        await message.answer("Этот навык уже прокачан до максимума!")
        return

    price = SKILLS[sk_id]['base_price'] * (level + 1)
    balance = data.get('balance', 0)
    if balance < price:
        await message.answer(f"Недостаточно средств. Нужно {price} сыроежек.")
        return

    await update_user_balance(chat_id, user_id, -price)
    skills[sk_id] = level + 1
    from user_manager import update_user_field
    await update_user_field(chat_id, user_id, 'skills', skills)

    await message.answer(f"🎉 Вы успешно прокачали навык <b>{SKILLS[sk_id]['name']}</b> до {level+1} уровня!")
