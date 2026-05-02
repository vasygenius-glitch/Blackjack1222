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

    # --- НОВАЯ ЛОГИКА ДОЛГОВ (ПЕРЕД ИГРОКАМИ И БАНКАМИ) ---
    debts = data.get('debts', {})
    debt_display = ""
    if debts:
        debt_list = []
        for lender_id_str, amount in debts.items():
            if amount > 0:
                if lender_id_str.startswith("bank_"):
                    banker_id = int(lender_id_str.split("_")[1])
                    bank_data = await get_bank_info(chat_id, banker_id)
                    lender_name = escape_html(bank_data.get('name', 'Банк')) if bank_data else 'Банк'
                    debt_list.append(f"🏦 <b>{lender_name}</b> ({amount} сыр.)")
                else:
                    try:
                        lender_data = await get_user_data(chat_id, int(lender_id_str))
                        lender_name = escape_html(lender_data.get('full_name', f"Юзер {lender_id_str}"))
                        debt_list.append(f"👤 <b>{lender_name}</b> ({amount} сыр.)")
                    except ValueError:
                        pass
        
        if debt_list:
            debt_display = f"\n💸 <b>Долги:</b> {', '.join(debt_list)}"
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

    # Скрываем банк если оффшор и мы смотрим чужой профиль
    if data.get('is_offshore', False) and message.from_user.id != target_id:
        bank_text = "🏦 В банке: <i>Скрыто (Оффшор)</i>\n\n"
    else:
        bank_text = f"🏦 В банке: <b>{bank_deposit}</b> сыр.\n\n"

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
        f"{bank_text}"
        f"🛡 Клан: {clan}\n"
        f"💍 Брак: {partner_text}\n\n"
        f"🚗 Машин: {cars}\n"
        f"🏢 Бизнесов: {biz}\n\n"
        f"💬 Сообщений в чате: {msg_count}"
    )

    await message.answer(text)

async def get_bank_info(chat_id: int, identifier):
    db = get_db()
    banks_ref = db.collection('chats').document(str(chat_id)).collection('banks')

    # Сначала пробуем по ID банкира
    try:
        banker_id = int(identifier)
        doc = await banks_ref.document(str(banker_id)).get()
        if doc.exists:
            data = doc.to_dict()
            data['banker_id'] = banker_id
            return data
    except ValueError:
        pass

    # Если не ID, ищем по имени банка
    search_name = str(identifier).lower()
    docs = await banks_ref.get()
    for doc in docs:
        b_data = doc.to_dict()
        b_name = b_data.get('name', '').lower()
        if b_name.startswith(search_name) or search_name in b_name:
            b_data['banker_id'] = int(doc.id)
            return b_data

    return None

async def create_or_update_bank(chat_id: int, banker_id: int, data: dict):
    db = get_db()
    bank_ref = db.collection('chats').document(str(chat_id)).collection('banks').document(str(banker_id))
    await bank_ref.set(data, merge=True)

@router.message(Command("bank"))
async def cmd_bank(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "🏦 <b>Банки Сыроежек</b>\n\n"
            "Вы можете вложить свои деньги в банк под процент.\n"
            "Команды:\n"
            "<code>/bank info [Название или ID]</code> - Информация о банке\n"
            "<code>/bank list</code> - Список всех банков в чате\n"
            "<code>/bank deposit [сумма] [Название или ID]</code>\n"
            "<code>/bank withdraw [сумма]</code> - Снять со своего вклада\n"
            "<code>/bank withdraw all</code> - Снять все деньги\n\n"
            "<i>(Вы можете иметь вклад только в одном банке одновременно.\nКаждый день хранения средств увеличивает ваш процент на +0.5%)</i>"
        )

    action = args[1].lower()

    if action == "list":
        db = get_db()
        banks_ref = db.collection('chats').document(str(chat_id)).collection('banks')
        docs = await banks_ref.get()
        if not docs:
            return await message.answer("🏦 В этом чате пока нет банков.")

        text = "🏦 <b>Список Банков:</b>\n\n"
        for doc in docs:
            b_data = doc.to_dict()
            rate = b_data.get('deposit_rate', 1.0)
            text += f"🏛 <b>{escape_html(b_data.get('name', 'Банк'))}</b>\n"
            text += f"ID Банкира: <code>{doc.id}</code>\n"
            text += f"Ставка по вкладу: <b>{rate}%</b> в день\n"
            text += f"Капитал: <b>{b_data.get('capital', 0)}</b> сыр.\n\n"
        return await message.answer(text)

    if action == "info":
        if len(args) < 3:
            return await message.answer("Укажите название банка или ID: <code>/bank info [Название]</code>")

        identifier = " ".join(args[2:])
        bank_data = await get_bank_info(chat_id, identifier)
        if not bank_data:
            return await message.answer("🏦 Банк не найден.")

        rate = bank_data.get('deposit_rate', 1.0)
        text = f"🏛 <b>{escape_html(bank_data.get('name', 'Банк'))}</b>\n\n"
        text += f"Владелец (ID): <code>{bank_data['banker_id']}</code>\n"
        text += f"Ставка по вкладу: <b>{rate}%</b> в день\n"
        text += f"Капитал банка: <b>{bank_data.get('capital', 0)}</b> сыр.\n"
        return await message.answer(text)

    if len(args) < 3: return await message.answer("Укажите сумму.")

    try:
        amount = int(args[2])
        if amount <= 0: return
    except: return

    data = await get_user_data(chat_id, user_id)
    current_deposit = data.get('bank_deposit', 0)
    current_banker_id = data.get('bank_name') # Храним ID банкира, где лежит вклад

    if action == "deposit":
        if len(args) < 4:
            return await message.answer("Укажите название банка или ID: <code>/bank deposit [сумма] [Название]</code>")

        identifier = " ".join(args[3:])
        bank_data = await get_bank_info(chat_id, identifier)

        if not bank_data:
            return await message.answer("🏦 Банк не найден.")

        target_banker_id = bank_data['banker_id']

        if current_banker_id and current_banker_id != target_banker_id and current_deposit > 0:
            return await message.answer("❌ У вас уже есть активный вклад в другом банке! Сначала снимите все средства.")

        if data.get('balance', 0) < amount:
            return await message.answer("Недостаточно средств на балансе.")

        # Списываем у игрока, добавляем в капитал банка
        await update_user_balance(chat_id, user_id, -amount)
        await update_user_field(chat_id, user_id, 'bank_deposit', current_deposit + amount)
        await update_user_field(chat_id, user_id, 'bank_name', target_banker_id)

        # Запоминаем время вклада (если первый раз или обновляем)
        if current_deposit == 0:
            await update_user_field(chat_id, user_id, 'deposit_start_time', int(time.time()))

        await create_or_update_bank(chat_id, target_banker_id, {'capital': bank_data.get('capital', 0) + amount})
        await message.answer(f"✅ Депозит пополнен на {amount} сыр. в банке <b>{escape_html(bank_data.get('name'))}</b>.\nВаш общий вклад: {current_deposit + amount}.")

    elif action == "withdraw":
        if args[2].lower() == "all":
            amount = current_deposit
            if amount <= 0:
                return await message.answer("У вас нет средств на банковском счете.")

        if current_deposit < amount:
            return await message.answer(f"На вашем вкладе только {current_deposit} сыроежек.")

        if not current_banker_id:
            # Для старых вкладов без привязки к банку (сделанных до обновления)
            await update_user_field(chat_id, user_id, 'bank_deposit', current_deposit - amount)
            await update_user_balance(chat_id, user_id, amount)
            return await message.answer(f"💸 Снято {amount} сыроежек со старого системного счета.")

        bank_data = await get_bank_info(chat_id, current_banker_id)
        if not bank_data:
            # Если банк удален, отдаем деньги из "воздуха" как гарантия ЦБ
            await update_user_field(chat_id, user_id, 'bank_deposit', current_deposit - amount)
            await update_user_balance(chat_id, user_id, amount)
            if current_deposit - amount == 0:
                await update_user_field(chat_id, user_id, 'bank_name', None)
            return await message.answer(f"💸 Ваш банк закрылся, но ЦБ гарантирует вклады. Снято {amount} сыроежек.")

        if bank_data.get('capital', 0) < amount:
            return await message.answer(" У банка недостаточно ликвидности (капитала), чтобы выдать вам деньги сейчас! Банкир выдал слишком много кредитов.")

        # Снимаем со вклада, списываем из капитала банка
        await update_user_field(chat_id, user_id, 'bank_deposit', current_deposit - amount)
        await update_user_balance(chat_id, user_id, amount)
        await create_or_update_bank(chat_id, current_banker_id, {'capital': bank_data.get('capital', 0) - amount})

        if current_deposit - amount == 0:
            await update_user_field(chat_id, user_id, 'bank_name', None) # Отвязываем от банка
            await update_user_field(chat_id, user_id, 'deposit_start_time', 0) # Сбрасываем срок лояльности

        await message.answer(f"💸 Снято {amount} сыроежек со счета.")
@router.message(F.text.lower().startswith("создать банк"))
async def cmd_create_bank(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker', False):
        return await message.answer("❌ Только официально назначенные Банкиры могут создавать банки.")

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer("Использование: <code>создать банк [Название]</code>")

    bank_name = escape_html(args[2])

    bank_data = await get_bank_info(chat_id, user_id)
    if bank_data:
        return await message.answer(f"❌ У вас уже есть банк: <b>{escape_html(bank_data.get('name'))}</b>")

    await create_or_update_bank(chat_id, user_id, {
        'name': bank_name,
        'capital': 0,
        'banker_name': escape_html(message.from_user.full_name)
    })

    await message.answer(f"🏛 <b>Банк успешно создан!</b>\nНазвание: {bank_name}\nТеперь игроки могут вкладывать деньги в ваш банк с помощью:\n<code>/bank deposit [сумма] {user_id}</code>")

# Удалено снятие прибыли, так как банкиры больше не могут выводить капитал банка напрямую себе

@router.message(Command("bankrate"))
async def cmd_bank_rate(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: <code>/bankrate [процент 3-13]</code>")

    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker', False):
        return await message.answer("❌ Вы не банкир.")

    try:
        rate = float(args[1])
        if rate < 3 or rate > 13:
            return await message.answer("Процент должен быть от 3 до 13.")
    except ValueError:
        return await message.answer("Процент должен быть числом.")

    bank_data = await get_bank_info(chat_id, user_id)
    if not bank_data:
        return await message.answer("❌ У вас нет открытого банка.")

    await create_or_update_bank(chat_id, user_id, {'deposit_rate': rate})
    await message.answer(f"📈 Процент по вкладам в вашем банке установлен на <b>{rate}%</b> в день.")


@router.message(Command("bank_offshore"))
async def cmd_bank_offshore(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    data = await get_user_data(chat_id, user_id)
    is_offshore = data.get('is_offshore', False)

    if is_offshore:
        await update_user_field(chat_id, user_id, 'is_offshore', False)
        await message.answer("🏝 Вы отключили оффшорный статус. Ваш банковский счет снова виден всем.")
    else:
        price = 500000
        if data.get('balance', 0) < price:
            return await message.answer(f"❌ Оформление оффшорного счета стоит {price} сыроежек. У вас недостаточно средств.")

        await update_user_balance(chat_id, user_id, -price)
        await update_user_field(chat_id, user_id, 'is_offshore', True)
        await message.answer(f"🏝 <b>Оффшорный счет активирован!</b>\nСписано {price} сыр. Теперь ваш вклад скрыт от других игроков в `/profile`.\n<i>(Банк будет снимать 0.5% от вашего депозита при начислении процентов за обслуживание)</i>")

@router.message(Command("bank_stats"))
async def cmd_bank_stats(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    data = await get_user_data(chat_id, user_id)
    if not data.get('is_banker', False):
        return await message.answer("❌ Эта команда доступна только банкирам.")

    bank_data = await get_bank_info(chat_id, user_id)
    if not bank_data:
        return await message.answer("❌ У вас нет открытого банка.")

    db = get_db()

    # Считаем вклады
    users_ref = db.collection('chats').document(str(chat_id)).collection('users')
    user_docs = await users_ref.get()

    total_deposits = 0
    total_depositors = 0
    total_loans_given = 0
    overdue_loans = 0

    import time
    current_time = time.time()

    for user_doc in user_docs:
        u_data = user_doc.to_dict()

        if str(u_data.get('bank_name')) == str(user_id):
            total_deposits += u_data.get('bank_deposit', 0)
            total_depositors += 1

        debts = u_data.get('debts', {})
        for k, v in debts.items():
            if k.startswith(f"bank_{user_id}_") and v > 0:
                total_loans_given += v
                parts = k.split("_")
                if len(parts) >= 3:
                    due_date = int(parts[2])
                    if current_time > due_date:
                        overdue_loans += v

    rate = bank_data.get('deposit_rate', 3.0)
    capital = bank_data.get('capital', 0)

    text = (
        f"📊 <b>Панель управления банком: {escape_html(bank_data.get('name'))}</b>\n\n"
        f"💰 <b>Ликвидность (Капитал):</b> {capital} сыр.\n"
        f"📈 <b>Ставка по вкладам:</b> {rate}%\n\n"
        f"👥 <b>Вкладчиков:</b> {total_depositors}\n"
        f"🏦 <b>Сумма на вкладах:</b> {total_deposits} сыр.\n\n"
        f"🤝 <b>Раздано кредитов:</b> {total_loans_given} сыр.\n"
        f"🚨 <b>Просроченных долгов:</b> {overdue_loans} сыр.\n"
    )

    await message.answer(text)
