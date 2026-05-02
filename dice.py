import asyncio
import secrets
from aiogram import Router, types
from aiogram.filters import Command
from user_manager import get_user_data, update_user_balance

router = Router()

async def schedule_delete(*messages, delay: int = 40):
    import asyncio
    await asyncio.sleep(delay)
    for msg in messages:
        try:
            if msg and hasattr(msg, 'delete'):
                await msg.delete()
        except:
            pass

@router.message(Command("dice"))
async def cmd_dice(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажите ставку: <code>/dice 100</code>")

    try:
        bet = int(args[1])
        if bet < 100 or bet > 50000000:
            raise ValueError
    except ValueError:
        return await message.answer("Ставка должна быть числом от 100 до 50,000,000 сыроежек.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    data = await get_user_data(chat_id, user_id)

    if data.get('balance', 0) - bet < -5000:
        return await message.answer("Ваш кредитный лимит (-5000) исчерпан. Пополните баланс.")

    rand = secrets.SystemRandom()
    player_roll = rand.randint(1, 6)
    bot_roll = rand.randint(1, 6)

    text = f"🎲 <b>Игра в кости</b>\n\nВы бросили: <b>{player_roll}</b>\nБот бросил: <b>{bot_roll}</b>\n\n"

    if player_roll > bot_roll:
        await update_user_balance(chat_id, user_id, bet)
        text += f"🎉 Вы победили! Выиграно: <b>{bet}</b> сыроежек."
    elif player_roll < bot_roll:
        await update_user_balance(chat_id, user_id, -bet)
        text += f"❌ Вы проиграли <b>{bet}</b> сыроежек."
    else:
        text += "🤝 Ничья! Ставка возвращена."

    msg = await message.answer(text)
    asyncio.create_task(schedule_delete(msg, message))
