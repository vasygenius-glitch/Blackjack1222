import asyncio
import random
import secrets
from aiogram import Router, types
from aiogram.filters import Command

from user_manager import get_user_data, update_user_balance, check_and_give_bonus
from chances import get_game_chance
from escape import escape_html

router = Router()

async def schedule_delete(*messages):
    import asyncio
    await asyncio.sleep(40)
    for msg in messages:
        try:
            if msg and hasattr(msg, 'delete'):
                await msg.delete()
        except:
            pass

secure_random = secrets.SystemRandom()

@router.message(Command("roulette"))
async def cmd_roulette(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    full_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, user_id, full_name)
    if data.get('is_banned', False):
        await message.answer("Вы забанены и не можете играть.")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer("Использование: <code>/roulette <ставка> <число от 1 до 36></code>\nПример: <code>/roulette 100 15</code>")
        return

    try:
        bet = int(args[1])
        guess = int(args[2])
        if bet < 100:
            await message.answer("Минимальная ставка — 100 сыроежек.")
            return
        if not (1 <= guess <= 36):
            await message.answer("Число должно быть от 1 до 36.")
            return
    except ValueError:
        await message.answer("Ставка и число должны быть целыми числами.")
        return

    bonus_given, receipt = await check_and_give_bonus(chat_id, user_id, full_name)
    bonus_text = f"🎁 Вы получили ежедневный бонус: {receipt.get('total', 0)} сыроежек!\n" if bonus_given else ""

    # Re-fetch data after bonus check
    data = await get_user_data(chat_id, user_id, full_name)
    balance = data.get('balance', 0)

    if balance - bet < -5000:
        await message.answer(f"{bonus_text}Ваш кредитный лимит (-5000) исчерпан. Пополните баланс.")
        return

    await update_user_balance(chat_id, user_id, -bet)

    # Проверка шансов (Подкрутка)
    chance = await get_game_chance('roulette')
    if chance != -1:
        is_forced_win = (secure_random.randint(1, 100) <= chance)
        if is_forced_win:
            # Даем победу (разброс от 0 до 4)
            diff = secure_random.randint(0, 4)
            result_number = guess + secure_random.choice([-diff, diff])
            if result_number < 1: result_number = 1
            if result_number > 36: result_number = 36
        else:
            # Принудительный проигрыш (разброс больше 4)
            result_number = secure_random.randint(1, 36)
            while abs(result_number - guess) <= 4:
                result_number = secure_random.randint(1, 36)
    else:
        result_number = secure_random.randint(1, 36)

    diff = abs(result_number - guess)

    if diff == 0:
        total_win = bet * 3
        multiplier_text = "x3 (Точное совпадение!)"
    elif diff <= 2:
        total_win = int(bet * 1.5)
        multiplier_text = "x1.5 (Разница 1-2 числа)"
    elif diff <= 4:
        total_win = int(bet * 1.1)
        multiplier_text = "x1.1 (Разница 3-4 числа)"
    else:
        total_win = 0
        multiplier_text = "Проигрыш (Слишком далеко)"

    if total_win > 0:
        profit = total_win - bet
        is_vip = data.get('is_vip', False)
        vip_bonus_text = ""
        if is_vip:
            vip_profit_bonus = int(profit * 0.1)
            profit += vip_profit_bonus
            vip_bonus_text = f" (👑 VIP бонус: +{vip_profit_bonus})"

        final_win_amount = bet + profit
        await update_user_balance(chat_id, user_id, final_win_amount)
        result_text = f"<b>Вы выиграли {profit} сыроежек!</b>{vip_bonus_text}"
    else:
        result_text = f"<b>Вы проиграли {bet} сыроежек!</b>"

    text = (
        f"{bonus_text}"
        f"🎯 Рулетка крутится...\n"
        f"Выпало число: <b>{result_number}</b> (Ваш выбор: {guess})\n\n"
        f"{result_text}\n"
        f"Множитель: {multiplier_text}"
    )

    msg = await message.answer(text)
    asyncio.create_task(schedule_delete(msg, message))
