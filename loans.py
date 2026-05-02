import time
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from escape import escape_html
from user_manager import get_user_data, update_user_balance, update_user_field
from profile_bank import get_bank_info, create_or_update_bank

router = Router()
active_loans = {}

@router.message(F.text.lower().startswith("кредит") | F.text.lower().startswith("/credit"))
async def cmd_credit(message: types.Message):
    chat_id = message.chat.id
    lender_id = message.from_user.id

    data = await get_user_data(chat_id, lender_id)
    if not data.get('is_banker', False):
        return await message.answer("❌ Только банкиры могут выдавать кредиты.")

    if not message.reply_to_message:
        return await message.answer("Сделайте реплай на сообщение игрока, которому хотите выдать кредит.")

    args = message.text.split()
    if len(args) < 4:
        return await message.answer("Использование: <code>кредит [сумма] [%] [срок в днях]</code>\nПример: <code>кредит 1000 10 7</code>\n\nВы можете добавить поручителя: <code>кредит [сумма] [%] [срок] [ID_поручителя]</code>")

    borrower_id = message.reply_to_message.from_user.id
    if lender_id == borrower_id:
        return await message.answer("Самому себе кредит выдать нельзя.")
    if message.reply_to_message.from_user.is_bot:
        return await message.answer("Ботам кредиты не нужны.")

    try:
        amount = int(args[1])
        percent = int(args[2])
        term_days = int(args[3])
        if amount <= 0 or percent < 0 or term_days <= 0:
            return
    except ValueError:
        return await message.answer("Сумма, процент и срок должны быть числами.")

    guarantor_id = None
    if len(args) >= 5:
        try:
            guarantor_id = int(args[4])
            if guarantor_id == borrower_id:
                return await message.answer("Заемщик не может быть поручителем самому себе.")
        except ValueError:
            return await message.answer("ID поручителя должен быть числом.")

    bank_data = await get_bank_info(chat_id, lender_id)
    if not bank_data:
        return await message.answer("❌ У вас еще не создан банк. Создайте его командой <code>создать банк [Название]</code>.")

    if bank_data.get('capital', 0) < amount:
        return await message.answer(f"❌ В капитале вашего банка недостаточно средств! Капитал: {bank_data.get('capital', 0)}")

    import uuid
    short_id = str(uuid.uuid4())[:8]
    loan_id = f"bk_{short_id}"
    active_loans[loan_id] = {
        'amount': amount,
        'percent': percent,
        'term_days': term_days,
        'chat_id': chat_id,
        'lender_id': lender_id,
        'borrower_id': borrower_id,
        'guarantor_id': guarantor_id,
        'original_principal': amount # Запоминаем изначальное тело кредита
    }

    builder = InlineKeyboardBuilder()
    builder.button(text="Взять кредит 🤝", callback_data=f"bk_yes_{short_id}")
    builder.button(text="Отказаться ❌", callback_data=f"bk_no_{short_id}")

    total_return = int(amount * (1 + percent / 100))
    bank_name = escape_html(bank_data.get('name', 'Неизвестный Банк'))

    borrower_data = await get_user_data(chat_id, borrower_id)
    credit_score = borrower_data.get('credit_score', 100)

    guarantor_text = f"\nПоручитель (ID): <code>{guarantor_id}</code>" if guarantor_id else ""

    await message.answer(
        f"💸 <b>Кредитный договор с банком «{bank_name}»!</b>\n\n"
        f"Заемщик: <b>{escape_html(message.reply_to_message.from_user.full_name)}</b> (Рейтинг: {credit_score}){guarantor_text}\n\n"
        f"Кредит на <b>{amount}</b> сыроежек под <b>{percent}%</b> на <b>{term_days}</b> дней.\n"
        f"Итого к возврату: <b>{total_return}</b> сыроежек.\n\n"
        f"Заемщик, согласны с условиями?",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("bk_yes_") | F.data.startswith("bk_no_"))
async def process_bank_loan(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    short_id = callback.data.split("_")[2]
    loan_id = f"bk_{short_id}"

    if loan_id not in active_loans:
        return await callback.answer("Это предложение устарело.", show_alert=True)

    loan_info = active_loans[loan_id]
    chat_id = loan_info['chat_id']
    lender_id = loan_info['lender_id']
    borrower_id = loan_info['borrower_id']

    if callback.from_user.id != borrower_id:
        return await callback.answer("Это предлагают не тебе!", show_alert=True)

    active_loans.pop(loan_id)

    if action == "no":
        return await callback.message.edit_text("❌ Клиент отказался брать кредит.")

    amount = loan_info['amount']
    percent = loan_info['percent']
    term_days = loan_info['term_days']
    guarantor_id = loan_info['guarantor_id']
    total_debt = int(amount * (1 + percent / 100))

    bank_data = await get_bank_info(chat_id, lender_id)
    if not bank_data or bank_data.get('capital', 0) < amount:
        return await callback.message.edit_text("❌ У банка уже не хватает капитала.")

    # Выдаем кредит из капитала банка
    await create_or_update_bank(chat_id, lender_id, {'capital': bank_data.get('capital', 0) - amount})
    await update_user_balance(chat_id, borrower_id, amount)

    borrower_data = await get_user_data(chat_id, borrower_id)
    debts = borrower_data.get('debts', {})
    
    due_date = int(time.time()) + (term_days * 86400)
    # Формат долга: bank_ID_DUEDATE_GUARANTORID_PRINCIPAL
    g_id_str = str(guarantor_id) if guarantor_id else "none"
    str_lender = f"bank_{lender_id}_{due_date}_{g_id_str}_{amount}"

    debts[str_lender] = debts.get(str_lender, 0) + total_debt
    
    await update_user_field(chat_id, borrower_id, 'debts', debts)

    await callback.message.edit_text(f"🤝 Кредит оформлен на {term_days} дн.!\nПолучено <b>{amount}</b> сыроежек.\nДолг банку: <b>{total_debt}</b> сыроежек.")

@router.message(F.text.lower().startswith("выплатить") | F.text.lower().startswith("вернуть"))
async def cmd_repay(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Сделай реплай на кредитора (или банкира), которому возвращаешь долг.")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажи сумму: выплатить [сумма]")

    try:
        amount = int(args[1])
        if amount <= 0: return
    except ValueError:
        return

    chat_id = message.chat.id
    borrower_id = message.from_user.id
    lender_id = message.reply_to_message.from_user.id

    borrower_data = await get_user_data(chat_id, borrower_id)
    debts = borrower_data.get('debts', {})

    str_lender_player = str(lender_id)

    target_debt_key = None

    # Ищем долг банку с любой датой или без даты (для старых долгов)
    for k, v in debts.items():
        if k.startswith(f"bank_{lender_id}") and v > 0:
            target_debt_key = k
            break

    if not target_debt_key and str_lender_player in debts and debts[str_lender_player] > 0:
        target_debt_key = str_lender_player

    if not target_debt_key:
        return await message.answer("Ты ничего не должен этому человеку/банку.")

    if borrower_data.get('balance', 0) < amount:
        return await message.answer("У тебя нет столько денег на балансе.")

    current_debt = debts[target_debt_key]

    # Обработка досрочного погашения и банковской комиссии
    banker_commission = 0
    discount_msg = ""
    if target_debt_key.startswith("bank_"):
        parts = target_debt_key.split("_")
        if len(parts) >= 5:
            due_date = int(parts[2])
            principal = int(parts[4])

            # Проверяем, отдается ли весь долг целиком
            if amount >= current_debt:
                current_time = time.time()
                # Если возвращаем сильно заранее (более 1 дня до конца срока)
                if due_date - current_time > 86400:
                    discount = int((current_debt - principal) * 0.2) # 20% скидка на проценты
                    if discount > 0:
                        current_debt -= discount
                        discount_msg = f"\n🎁 <i>Скидка за досрочное погашение: -{discount} сыр.</i>"

                # Комиссия банкира 10% от выплаченных процентов (если кредит отдан полностью)
                profit_margin = current_debt - principal
                if profit_margin > 0:
                    banker_commission = int(profit_margin * 0.1)

    repay_amount = min(amount, current_debt)
    await update_user_balance(chat_id, borrower_id, -repay_amount)

    if target_debt_key.startswith("bank_"):
        # Возврат банку в капитал
        bank_data = await get_bank_info(chat_id, lender_id)
        if bank_data:
            # Начисляем капитал банку (минус премия банкиру)
            await create_or_update_bank(chat_id, lender_id, {'capital': bank_data.get('capital', 0) + (repay_amount - banker_commission)})
            # Начисляем премию банкиру на личный счет
            if banker_commission > 0:
                await update_user_balance(chat_id, lender_id, banker_commission)
    else:
        # Возврат обычному игроку
        await update_user_balance(chat_id, lender_id, repay_amount)

    debts[target_debt_key] -= repay_amount

    # Повышаем рейтинг при полном закрытии долга
    rating_msg = ""
    if debts[target_debt_key] <= 0:
        del debts[target_debt_key]
        if target_debt_key.startswith("bank_"):
            credit_score = borrower_data.get('credit_score', 100)
            new_score = min(500, credit_score + 10)
            await update_user_field(chat_id, borrower_id, 'credit_score', new_score)
            rating_msg = f"\n📈 Ваш кредитный рейтинг повышен до <b>{new_score}</b>!"

    await update_user_field(chat_id, borrower_id, 'debts', debts)
    await message.answer(f"✅ Ты вернул <b>{repay_amount}</b> сыроежек кредитору.{discount_msg}\nОстаток долга: <b>{debts.get(target_debt_key, 0)}</b> сыроежек.{rating_msg}")
