import time
import secrets
from aiogram import Router, types, Bot, F
from escape import escape_html
from user_manager import get_user_data, update_user_balance, update_user_field

router = Router()

@router.message(F.text.lower().startswith("украсть") | F.text.lower().startswith("/steal"))
async def cmd_steal(message: types.Message, bot: Bot):
    if not message.reply_to_message:
        return await message.answer("Сделайте реплай на сообщение того, кого хотите ограбить.")

    chat_id = message.chat.id
    user_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id

    if user_id == target_id: return await message.answer("Вы не можете украсть у себя.")
    if message.reply_to_message.from_user.is_bot: return await message.answer("У бота денег нет.")

    from config import CREATOR_ID
    if int(target_id) == int(CREATOR_ID):
        return await message.answer("Невозможно ограбить Создателя!")

    try:
        target_member = await bot.get_chat_member(chat_id, target_id)
        if target_member.status in['administrator', 'creator']:
            return await message.answer("Невозможно ограбить Администрацию!")
    except: pass

    data = await get_user_data(chat_id, user_id)
    last_steal = data.get('last_steal_time', 0)
    current_time = int(time.time())

    if current_time - last_steal < 3600: # 1 hour cooldown
        return await message.answer("Вы уже пытались воровать недавно. Залягте на дно (кулдаун 1 час).")

    await update_user_field(chat_id, user_id, 'last_steal_time', current_time)

    target_data = await get_user_data(chat_id, target_id)
    target_balance = target_data.get('balance', 0)

    if target_balance <= 0:
        return await message.answer("У этого бедолаги пустые карманы, воровать нечего.")

    rand = secrets.SystemRandom()
    stealth_bonus = data.get('skills', {}).get('stealth', 0) * 0.05
    success_chance = 0.3 + stealth_bonus # Base 30%

    # Защита от ограбления банкиров
    if target_data.get('is_banker') and target_data.get('bank_security'):
        success_chance /= 2.0 # Шанс режется в 2 раза

    if rand.random() < success_chance:
        steal_amount = int(target_balance * rand.uniform(0.01, 0.05)) # Steal 1-5%
        if steal_amount == 0: steal_amount = 1

        await update_user_balance(chat_id, user_id, steal_amount)
        await update_user_balance(chat_id, target_id, -steal_amount)

        await message.answer(f"🥷 <b>Успех!</b>\nВы незаметно вытащили из кармана <b>{escape_html(message.reply_to_message.from_user.full_name)}</b> сумму в <b>{steal_amount}</b> сыроежек!")
    else:
        penalty = int(target_balance * 0.02) # Penalty 2%
        if penalty == 0: penalty = 50

        user_balance = data.get('balance', 0)
        actual_penalty = penalty if user_balance <= 0 else min(penalty, user_balance)

        await update_user_balance(chat_id, user_id, -actual_penalty, is_debt_repayment=True)
        await update_user_balance(chat_id, target_id, actual_penalty)

        if target_data.get('is_banker') and target_data.get('bank_security'):
            await message.answer(f"🚨 <b>Провал! Вооруженная охрана банка скрутила вас!</b>\nВ качестве компенсации вы отдаете <b>{actual_penalty}</b> сыроежек в капитал банка.")
        else:
            await message.answer(f"🚨 <b>Провал!</b>\nВас поймали за руку! В качестве компенсации вы отдаете <b>{actual_penalty}</b> сыроежек жертве.")