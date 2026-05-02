import time
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from db import get_db
from escape import escape_html
from user_manager import get_user_data, update_user_balance, update_user_field
from shop import ITEMS

router = Router()

@router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    chat_id = message.chat.id
    # Определяем, чей профиль смотрим (свой или чужой через реплай)
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = escape_html(message.reply_to_message.from_user.full_name)
    else:
        target_id = message.from_user.id
        target_name = escape_html(message.from_user.full_name)

    data = await get_user_data(chat_id, target_id, target_name)

    vip_status = "💎 VIP" if data.get('is_vip') else "Обычный"
    balance = data.get('balance', 0)
    rep = data.get('reputation', 0)
    clan = escape_html(data.get('clan', 'Нет'))
    warns = len(data.get('warns', []))
    
    # Счётчик эскорта
    escort_count = data.get('escort_count', 0)
    escort_text = f"\n🔞 Выебан(а): {escort_count} раз" if escort_count > 0 else ""

    # --- НОВАЯ ЛОГИКА ДОЛГОВ (ПЕРЕД ИГРОКАМИ) ---
    debts = data.get('debts', {})
    debt_display = ""
    if debts:
        debt_list = []
        for lender_id_str, amount in debts.items():
            if amount > 0:
                # Получаем данные кредитора, чтобы узнать его имя
                lender_data = await get_user_data(chat_id, int(lender_id_str))
                lender_name = escape_html(lender_data.get('full_name', f"Юзер {lender_id_str}"))
                debt_list.append(f"<b>{lender_name}</b> ({amount} сыр.)")
        
        if debt_list:
            debt_display = f"\n💸 <b>Брал(а) в долг у:</b> {', '.join(debt_list)}"
    # --------------------------------------------

    # Брак
    partner_id = data.get('partner')
    partner_text = "Нет"
    if partner_id:
        p_data = await get_user_data(chat_id, partner_id)
        partner_text = escape_html(p_data.get('full_name', f"ID: {partner_id}"))

    # Имущество
    inventory = data.get('inventory', {})
    cars = sum(v for k, v in inventory.items() if ITEMS.get(k, {}).get('cat') == 'cars')
    biz = sum(v for k, v in inventory.items() if ITEMS.get(k, {}).get('cat') == 'biz')

    bank_deposit = data.get('bank_deposit', 0)

    # Статистика сообщений (из отдельной коллекции)
    db = get_db()
    stats_doc = await db.collection('chats').document(str(chat_id)).collection('stats').document(str(target_id)).get()
    msg_count = stats_doc.to_dict().get('all_time', 0) if stats_doc.exists else 0

    bio = escape_html(data.get('bio', 'Нет описания.'))

    text = (
        f"👤 <b>Профиль: {target_name}</b>\n"
        f"<i>{bio}</i>\n\n"
        f"Статус: {vip_status}\n"
        f"Репутация: {rep} 📈\n"
        f"Предупреждения: {warns}/3 ⚠️{escort_text}\n"
        f"{debt_display}\n" # Список реальных долгов перед людьми
        f"💰 Баланс: <b>{balance}</b> сыр.\n"
        f"🏦 В банке: <b>{bank_deposit}</b> сыр.\n\n"
        f"🛡 Клан: {clan}\n"
        f"💍 Брак: {partner_text}\n\n"
        f"🚗 Машин: {cars}\n"
        f"🏢 Бизнесов: {biz}\n\n"
        f"💬 Сообщений в чате: {msg_count}"
    )

    await message.answer(text)

@router.message(Command("bank"))
async def cmd_bank(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "🏦 <b>Банк Сыроежек</b>\n\n"
            "Минимальный вклад: 10.000.000\n"
            "Команды:\n"
            "<code>/bank deposit [сумма]</code>\n"
            "<code>/bank withdraw [сумма]</code>"
        )

    action = args[1].lower()
    if len(args) < 3: return await message.answer("Укажите сумму.")

    try:
        amount = int(args[2])
        if amount <= 0: return
    except: return

    data = await get_user_data(chat_id, user_id)
    current_deposit = data.get('bank_deposit', 0)

    if action == "deposit":
        if amount < 10000000 and current_deposit == 0:
            return await message.answer("Минимальный первоначальный вклад: 10.000.000 сыроежек.")
        if data.get('balance', 0) < amount:
            return await message.answer("Недостаточно средств на балансе.")

        await update_user_balance(chat_id, user_id, -amount)
        await update_user_field(chat_id, user_id, 'bank_deposit', current_deposit + amount)
        await message.answer(f"✅ Депозит пополнен на {amount} сыр. Всего: {current_deposit + amount}.")

    elif action == "withdraw":
        if current_deposit < amount:
            return await message.answer(f"В банке только {current_deposit} сыроежек.")

        await update_user_field(chat_id, user_id, 'bank_deposit', current_deposit - amount)
        await update_user_balance(chat_id, user_id, amount)
        await message.answer(f"💸 Снято {amount} сыроежек со счета.")