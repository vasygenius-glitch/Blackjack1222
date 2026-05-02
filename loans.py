import time
from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from escape import escape_html
from user_manager import get_user_data, update_user_balance, update_user_field

router = Router()
active_loans = {}

@router.message(F.text.lower().startswith("долг") | F.text.lower().startswith("/loan"))
async def cmd_loan(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Сделай реплай на того, кому даешь в долг.")

    args = message.text.split()
    if len(args) < 3:
        return await message.answer("Пиши так: долг [сумма] [процент]\nПример: долг 1000 10")

    chat_id = message.chat.id
    lender_id = message.from_user.id
    borrower_id = message.reply_to_message.from_user.id

    if lender_id == borrower_id:
        return await message.answer("Самому себе в долг не даем.")
    if message.reply_to_message.from_user.is_bot:
        return await message.answer("Ботам деньги не нужны.")

    try:
        amount = int(args[1])
        percent = int(args[2])
        if amount <= 0 or percent < 0:
            return
    except:
        return await message.answer("Сумма и процент должны быть числами.")

    lender_data = await get_user_data(chat_id, lender_id)
    if lender_data.get('balance', 0) < amount:
        return await message.answer("У тебя нет таких денег на балансе.")

    loan_id = f"loan_{chat_id}_{lender_id}_{borrower_id}_{int(time.time())}"
    active_loans[loan_id] = {'amount': amount, 'percent': percent}

    builder = InlineKeyboardBuilder()
    builder.button(text="Взять в долг 🤝", callback_data=f"loan_yes_{loan_id}")
    builder.button(text="Отказаться ❌", callback_data=f"loan_no_{loan_id}")

    total_return = int(amount * (1 + percent / 100))

    await message.answer(
        f"💸 <b>Кредитный договор!</b>\n\n"
        f"<b>{escape_html(message.from_user.full_name)}</b> предлагает в долг <b>{amount}</b> сыроежек под <b>{percent}%</b>.\n"
        f"Итого к возврату: <b>{total_return}</b> сыроежек.\n\n"
        f"<b>{escape_html(message.reply_to_message.from_user.full_name)}</b>, согласен взять деньги?",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("loan_yes_") | F.data.startswith("loan_no_"))
async def process_loan(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    loan_id = callback.data.replace(f"loan_{action}_", "")
    parts = loan_id.split("_")
    chat_id = int(parts[1])
    lender_id = int(parts[2])
    borrower_id = int(parts[3])

    if callback.from_user.id != borrower_id:
        return await callback.answer("Это предлагают не тебе!", show_alert=True)

    if loan_id not in active_loans:
        return await callback.answer("Это предложение устарело.", show_alert=True)

    loan_info = active_loans.pop(loan_id)

    if action == "no":
        return await callback.message.edit_text("❌ Заемщик отказался брать в долг.")

    amount = loan_info['amount']
    percent = loan_info['percent']
    total_debt = int(amount * (1 + percent / 100))

    lender_data = await get_user_data(chat_id, lender_id)
    if lender_data.get('balance', 0) < amount:
        return await callback.message.edit_text("❌ У кредитора уже не хватает денег.")

    await update_user_balance(chat_id, lender_id, -amount)
    await update_user_balance(chat_id, borrower_id, amount)

    borrower_data = await get_user_data(chat_id, borrower_id)
    debts = borrower_data.get('debts', {})
    
    str_lender = str(lender_id)
    debts[str_lender] = debts.get(str_lender, 0) + total_debt
    
    await update_user_field(chat_id, borrower_id, 'debts', debts)

    await callback.message.edit_text(f"🤝 Сделка состоялась!\nПолучено <b>{amount}</b> сыроежек.\nДолг перед кредитором: <b>{total_debt}</b> сыроежек.")

@router.message(F.text.lower().startswith("выплатить") | F.text.lower().startswith("вернуть"))
async def cmd_repay(message: types.Message):
    if not message.reply_to_message:
        return await message.answer("Сделай реплай на кредитора, которому возвращаешь долг.")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Укажи сумму: выплатить [сумма]")

    try:
        amount = int(args[1])
        if amount <= 0: return
    except:
        return

    chat_id = message.chat.id
    borrower_id = message.from_user.id
    lender_id = message.reply_to_message.from_user.id
    str_lender = str(lender_id)

    borrower_data = await get_user_data(chat_id, borrower_id)
    debts = borrower_data.get('debts', {})

    if str_lender not in debts or debts[str_lender] <= 0:
        return await message.answer("Ты ничего не должен этому человеку.")

    if borrower_data.get('balance', 0) < amount:
        return await message.answer("У тебя нет столько денег на балансе.")

    current_debt = debts[str_lender]
    repay_amount = min(amount, current_debt)

    await update_user_balance(chat_id, borrower_id, -repay_amount)
    await update_user_balance(chat_id, lender_id, repay_amount)

    debts[str_lender] -= repay_amount
    if debts[str_lender] <= 0:
        del debts[str_lender]

    await update_user_field(chat_id, borrower_id, 'debts', debts)
    await message.answer(f"✅ Ты вернул <b>{repay_amount}</b> сыроежек кредитору.\nОстаток долга: <b>{debts.get(str_lender, 0)}</b> сыроежек.")