from aiogram import Router, types
from aiogram.filters import Command
from db import get_db
from user_manager import update_user_balance
from creator import is_creator
from escape import escape_html

router = Router()

@router.message(Command("createpromo"))
async def cmd_createpromo(message: types.Message):
    if not is_creator(message):
        return

    args = message.text.split()
    if len(args) < 4:
        await message.answer("Использование: <code>/createpromo <код> <награда> <кол-во активаций></code>")
        return

    code = args[1]
    try:
        reward = int(args[2])
        max_activations = int(args[3])
    except ValueError:
        await message.answer("Награда и количество активаций должны быть числами.")
        return

    db = get_db()
    ref = db.collection('bot_settings').document('promocodes').collection('active').document(code)

    await ref.set({
        'reward': reward,
        'max_activations': max_activations,
        'used_by': []
    })

    await message.answer(f"✅ Промокод <b>{code}</b> успешно создан!\nНаграда: {reward} сыроежек\nКоличество активаций: {max_activations}")

@router.message(Command("promo"))
async def cmd_promo(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите промокод: <code>/promo КОД</code>")
        return

    code = args[1]
    chat_id = message.chat.id
    user_id = message.from_user.id

    db = get_db()
    ref = db.collection('bot_settings').document('promocodes').collection('active').document(code)
    doc = await ref.get()

    if not doc.exists:
        await message.answer("❌ Такого промокода не существует или он был удален.")
        return

    data = doc.to_dict()
    used_by = data.get('used_by', [])
    max_activations = data.get('max_activations', 0)
    reward = data.get('reward', 0)

    if user_id in used_by:
        await message.answer("❌ Вы уже активировали этот промокод!")
        return

    if len(used_by) >= max_activations:
        await message.answer("❌ Этот промокод больше не действителен (превышен лимит активаций).")
        return

    used_by.append(user_id)
    await ref.update({'used_by': used_by})

    await update_user_balance(chat_id, user_id, reward)
    await message.answer(f"🎉 Вы успешно активировали промокод <b>{code}</b> и получили <b>{reward}</b> сыроежек!")
