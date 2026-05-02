import io
import asyncio
import random
import contextlib
import time
import logging
from html import escape as escape_html  # Исправлен импорт (встроенная библиотека python)
from typing import Dict, Any

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import BufferedInputFile, InputMediaPhoto  # Добавлен InputMediaPhoto для real-time

# Если у тебя есть свои модули, они остаются тут
from db import get_db

# Настройка роутера для обработки сообщений и колбэков биржи
router = Router()

# Форматирование чисел: 1.000.000
def fmt(num: float | int) -> str:
    """
    Форматирует число, добавляя разделители тысяч.
    Например: 1000000 превращается в 1.000.000
    """
    try:
        return f"{int(num):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"

# ============================================================================
# БЛОК 1: РАБОТА С БАЗОЙ ДАННЫХ (FIRESTORE) И ЖИВОЙ РЫНОК
# ============================================================================

async def get_crypto_config() -> Dict[str, Any]:
    """
    Получает конфигурацию криптобиржи.
    Листинг теперь установлен в 0 (полностью бесплатно).
    """
    db = get_db()
    try:
        doc = await db.collection('bot_settings').document('crypto_config').get()
        if doc.exists:
            return doc.to_dict()
            
        # Устанавливаем стоимость листинга 0 по умолчанию
        default_config = {"listing_price": 0}
        await db.collection('bot_settings').document('crypto_config').set(default_config)
        return default_config
    except Exception as e:
        logging.error(f"Ошибка конфига: {e}")
        return {"listing_price": 0}

async def update_crypto_config(field: str, value: Any) -> bool:
    """
    Точечно обновляет поле в конфигурации биржи.
    """
    db = get_db()
    try:
        await db.collection('bot_settings').document('crypto_config').set({field: value}, merge=True)
        return True
    except Exception as e:
        logging.error(f"Ошибка обновления конфига: {e}")
        return False

async def get_all_coins() -> Dict[str, Any]:
    """
    Получает список всех существующих монет.
    НОВАЯ СИСТЕМА: 
    - Цена стартует рандомно от 100 до 500.
    - Раз в 10 минут (600 секунд) рандомно (1 или 0) чуть-чуть падает или растет.
    """
    db = get_db()
    try:
        doc = await db.collection('bot_settings').document('crypto_coins').get()
        if doc.exists:
            data = doc.to_dict()
            coins = data.get('coins', {})
            last_update = data.get('last_update', 0)
            current_time = int(time.time())
            
            # ТИК РЫНКА: Каждые 10 минут (600 секунд)
            if last_update > 0 and current_time - last_update >= 600:
                elapsed = current_time - last_update
                # Считаем, сколько тиков по 10 минут прошло
                ticks = min(elapsed // 600, 100) # Ограничим до 100, чтобы не лагало, если бот спал месяц
                
                if ticks > 0:
                    for _ in range(ticks):
                        for cid, coin in coins.items():
                            # Если монета почему-то пустая, даем ей старт от 100 до 500
                            prices = coin.setdefault("prices", [random.randint(100, 500)])
                            last_price = prices[-1] if prices else random.randint(100, 500)
                            
                            # =======================================================
                            # ЧИСТЫЙ 50/50 РАНДОМ (1 или 0)
                            # =======================================================
                            is_up = random.choice([0, 1])
                            
                            # Чуть-чуть (от 1% до 5%)
                            percent_change = random.uniform(0.01, 0.05)
                            change = int(last_price * percent_change)
                            
                            # Если цена слишком маленькая и процент дал 0, двигаем хотя бы на 1-3
                            if change == 0: 
                                change = random.randint(1, 3)
                                
                            if is_up == 1:
                                new_price = last_price + change
                            else:
                                new_price = last_price - change
                                
                            new_price = max(1, new_price)
                            
                            prices.append(new_price)
                            if len(prices) > 30:
                                prices.pop(0)
                                
                            coin["prices"] = prices
                            
                    # Сохраняем новые графики и обновляем время
                    # Вычитаем остаток, чтобы таймер шел ровно
                    new_last_update = current_time - (elapsed % 600)
                    await db.collection('bot_settings').document('crypto_coins').set({
                        'coins': coins,
                        'last_update': new_last_update
                    }, merge=True)
                    
            return coins
            
        # Заглушка, если база вообще пустая (самый первый запуск)
        current_time = int(time.time())
        default_coins = {
            "chsyr": {"name": "Китайская Сыроежка", "ticker": "CH_SYR", "prices":[random.randint(100, 500)], "creator": 0},
            "espsyr": {"name": "Испанская Сыроежка", "ticker": "ESP_SYR", "prices":[random.randint(100, 500)], "creator": 0}
        }
        await db.collection('bot_settings').document('crypto_coins').set({
            'coins': default_coins,
            'last_update': current_time
        }, merge=True)
        return default_coins
    except Exception as e:
        logging.error(f"Ошибка получения монет: {e}")
        return {}

async def update_coins(coins_dict: Dict[str, Any]) -> bool:
    """
    Сохраняет актуальное состояние всех монет в базу данных.
    """
    db = get_db()
    try:
        # ОБЯЗАТЕЛЬНО merge=True, чтобы не стереть счетчик времени (last_update)
        await db.collection('bot_settings').document('crypto_coins').set({'coins': coins_dict}, merge=True)
        return True
    except Exception as e:
        logging.error(f"Ошибка сохранения монет: {e}")
        return False

# ============================================================================
# БЛОК 2: ГЕНЕРАЦИЯ ГРАФИКОВ (MATPLOTLIB)
# ============================================================================

def _generate_single_chart_sync(coin_name: str, prices: list) -> bytes:
    """
    Синхронная функция генерации графика монеты.
    """
    if not prices:
        prices =[0]
        
    is_growing = prices[-1] >= prices[0]
    line_color = '#00FFA3' if is_growing else '#FF3B30'
    bg_color = '#121212'
    
    fig = Figure(figsize=(7, 4.5), dpi=100)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    
    x = list(range(len(prices)))
    volumes =[abs(prices[i] - prices[i-1]) * 1500 if i > 0 else 5000 for i in x]
    vol_colors =['#00FFA3' if i == 0 or prices[i] >= prices[i-1] else '#FF3B30' for i in x]
    
    ax2 = ax.twinx()
    ax2.bar(x, volumes, color=vol_colors, alpha=0.2, width=0.6)
    ax2.set_ylim(0, max(volumes) * 3 if max(volumes) > 0 else 100)
    ax2.axis('off')
    
    sma =[sum(prices[max(0, i-2):i+1])/len(prices[max(0, i-2):i+1]) for i in x]
    ax.plot(x, sma, color='#666666', linestyle=':', linewidth=1.2, alpha=0.8)
    
    for alpha, width in[(0.05, 10), (0.1, 6), (0.2, 3)]:
        ax.plot(x, prices, color=line_color, linewidth=width, alpha=alpha)
        
    ax.plot(x, prices, color=line_color, linewidth=2, zorder=5)
    ax.fill_between(x, prices, min(prices) * 0.9, color=line_color, alpha=0.05)
    
    ax.text(
        x[-1], prices[-1], f'  {fmt(prices[-1])}', 
        color='white', fontsize=10, fontweight='bold', 
        bbox=dict(facecolor=line_color, alpha=0.4, edgecolor='none', boxstyle='round,pad=0.3')
    )
    
    ax.grid(color='#2A2A2A', linestyle='-', linewidth=0.5, alpha=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(axis='both', colors='#888888', labelsize=9)
    ax.set_title(f"DATA: {coin_name}", color='white', fontsize=14, pad=20, fontweight='bold', loc='left')
    
    fig.tight_layout()
    buf = io.BytesIO()
    canvas.print_png(buf)
    buf.seek(0)
    
    # Очистка без использования plt.close, чтобы не ломать многопоточность
    ax.clear()
    fig.clear()
    return buf.read()

def _generate_global_chart_sync(coins_dict: Dict[str, Any]) -> bytes:
    """
    Генерация глобального индекса по топовым монетам.
    """
    bg_color = '#121212'
    colors =['#00FFA3', '#FF3B30', '#00B8FF', '#FFD600', '#FF00FF']
    fig = Figure(figsize=(8, 5), dpi=100)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    
    for idx, (coin_id, data) in enumerate(list(coins_dict.items())[:5]):
        prices = data["prices"]
        if not prices:
            continue
        x = range(len(prices))
        color = colors[idx % len(colors)]
        ax.plot(x, prices, color=color, linewidth=2.5, alpha=0.8, label=data["ticker"])
    
    ax.grid(color='#2A2A2A', linestyle='-', linewidth=0.5, alpha=0.7)
    ax.tick_params(axis='both', colors='#888888', labelsize=9)
    ax.set_title("GLOBAL MARKET INDEX", color='white', fontsize=16, pad=20, fontweight='bold')
    
    legend = ax.legend(facecolor='#1A1A1A', edgecolor='#333333', fontsize=9, loc='upper left')
    for text in legend.get_texts(): 
        text.set_color('white')
    
    fig.tight_layout()
    buf = io.BytesIO()
    canvas.print_png(buf)
    buf.seek(0)
    
    ax.clear()
    fig.clear()
    return buf.read()

async def generate_chart_async(coin_name: str, prices: list) -> bytes:
    return await asyncio.to_thread(_generate_single_chart_sync, coin_name, prices)

async def generate_global_chart_async(coins_dict: dict) -> bytes:
    return await asyncio.to_thread(_generate_global_chart_sync, coins_dict)

# ============================================================================
# БЛОК 3: УТИЛИТЫ И ПРОВЕРКИ ПРАВ
# ============================================================================

async def is_admin(message: types.Message) -> bool:
    """Проверяет, является ли пользователь администратором группы."""
    try:
        admins = await message.chat.get_administrators()
        return any(admin.user.id == message.from_user.id for admin in admins)
    except Exception as e:
        logging.warning(f"Ошибка проверки администратора: {e}")
        return False

async def check_ban(chat_id: int, user_id: int) -> bool:
    """Проверяет наличие блокировки доступа к крипте."""
    from user_manager import get_user_data
    try:
        data = await get_user_data(chat_id, user_id)
        return data.get('crypto_banned', False)
    except Exception as e:
        logging.error(f"Ошибка проверки бана: {e}")
        return False

async def smart_edit(callback: types.CallbackQuery, text: str, reply_markup):
    """
    Универсальная функция: если в сообщении фото, удаляет его и шлет текст. 
    Если фото нет, просто редактирует текст. Это чинит навигацию.
    """
    if callback.message.photo:
        await callback.message.delete()
        return await callback.message.answer(text, reply_markup=reply_markup)
        
    with contextlib.suppress(Exception):
        await callback.message.edit_text(text, reply_markup=reply_markup)

# ============================================================================
# БЛОК 4: АДМИНИСТРАТИВНЫЕ КОМАНДЫ
# ============================================================================

@router.message(F.text.lower().startswith("бан крипты"))
async def cmd_crypto_ban(message: types.Message):
    if not await is_admin(message):
        return
        
    if not message.reply_to_message:
        return
        
    from user_manager import update_user_field
    target_id = message.reply_to_message.from_user.id
    
    await update_user_field(message.chat.id, target_id, 'crypto_banned', True)
    await message.answer(f"🔨 <b>{message.reply_to_message.from_user.full_name}</b> забанен на бирже.")

@router.message(F.text.lower().startswith("разбан крипты"))
async def cmd_crypto_unban(message: types.Message):
    if not await is_admin(message):
        return
        
    if not message.reply_to_message:
        return
        
    from user_manager import update_user_field
    target_id = message.reply_to_message.from_user.id
    
    await update_user_field(message.chat.id, target_id, 'crypto_banned', False)
    await message.answer(f"✅ <b>{message.reply_to_message.from_user.full_name}</b> разбанен на бирже.")

@router.message(Command("cr_crash"))
async def cmd_cr_crash(message: types.Message):
    """Админская команда для искусственного обрушения курса монеты."""
    if not await is_admin(message): 
        return
        
    try:
        ticker = message.text.split()[1].lower()
        coins = await get_all_coins()
        
        if ticker in coins:
            coin = coins[ticker]
            old_p = coin["prices"][-1]
            
            new_price = max(1, int(old_p * random.uniform(0.01, 0.10)))
            coin["prices"].append(new_price)
            
            if len(coin["prices"]) > 30: 
                coin["prices"].pop(0)
                
            await update_coins(coins)
            await message.answer(f"📉📉📉 ТОТАЛЬНЫЙ КРАХ! Рынок в ужасе! {ticker.upper()} рухнул до {fmt(new_price)} сыр.")
        else:
            await message.answer("❌ Монета не найдена в базе данных.")
    except IndexError:
        await message.answer("⚠️ Использование: /cr_crash [ТИКЕР]")
    except Exception as e:
        logging.error(f"Ошибка при краше: {e}")

@router.message(Command("cr_price"))
async def cmd_cr_price(message: types.Message):
    """Админская команда для ручного изменения (пампа/дампа) курса монеты."""
    if not await is_admin(message): 
        return
        
    try:
        parts = message.text.split()
        if len(parts) < 3:
            return await message.answer("⚠️ Использование: /cr_price[ТИКЕР][НОВАЯ_ЦЕНА]\n💡 <i>Можно + или -</i>")
            
        ticker = parts[1].lower()
        val_str = parts[2]
        
        coins = await get_all_coins()
        
        if ticker in coins:
            coin = coins[ticker]
            old_p = coin["prices"][-1]
            
            if val_str.startswith('+'):
                new_price = old_p + int(val_str[1:])
            elif val_str.startswith('-'):
                new_price = old_p - int(val_str[1:])
            else:
                new_price = int(val_str)
                
            new_price = max(1, new_price)
            
            coin["prices"].append(new_price)
            
            if len(coin["prices"]) > 30: 
                coin["prices"].pop(0)
                
            await update_coins(coins)
            
            if new_price > old_p:
                await message.answer(f"🚀 Админский ПАМП! Курс {ticker.upper()} взлетел до {fmt(new_price)} сыр.")
            elif new_price < old_p:
                await message.answer(f"📉 Админский ДАМП! Курс {ticker.upper()} опущен до {fmt(new_price)} сыр.")
            else:
                await message.answer(f"⚖️ Курс {ticker.upper()} установлен ровно на {fmt(new_price)} сыр.")
        else:
            await message.answer("❌ Монета не найдена в базе данных.")
            
    except ValueError:
        await message.answer("❌ Укажите корректное число для цены.")
    except Exception as e:
        logging.error(f"Ошибка при изменении курса: {e}")

# ============================================================================
# БЛОК 5: ТОРГОВЫЕ ОПЕРАЦИИ И КОШЕЛЕК
# ============================================================================

@router.message(Command("createcoin"))
async def cmd_create_coin(message: types.Message):
    """Создание новой криптовалюты со случайной стартовой ценой (от 100 до 500)."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if await check_ban(chat_id, user_id): 
        return
        
    try:
        # Теперь ожидаем только ТИКЕР и НАЗВАНИЕ (цена генерируется сама)
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3: 
            raise ValueError("Недостаточно аргументов.")
            
        ticker = parts[1].lower()[:8]
        name = escape_html(parts[2][:32])
        
        # Рандомная цена старта от 100 до 500
        start_price = random.randint(100, 500)
            
        coins = await get_all_coins()
        if ticker in coins: 
            return await message.answer("❌ Этот тикер уже занят другой монетой.")
            
        user_coins = sum(1 for c in coins.values() if c.get('creator') == user_id)
        if user_coins >= 2: 
            return await message.answer("❌ Достигнут лимит: вы можете создать максимум 2 монеты.")
        
        coins[ticker] = {
            "name": name, 
            "ticker": ticker.upper(), 
            "prices":[start_price], 
            "creator": user_id
        }
        
        await update_coins(coins)
        
        await message.answer(
            f"🚀 Монета <b>{name}</b> ({ticker.upper()}) успешно залистена на биржу!\n"
            f"💰 Стартовая цена (случайная): {fmt(start_price)} сыр.\n"
            f"🆓 Стоимость листинга: 0 сыр (Бесплатно)"
        )
    except ValueError: 
        await message.answer("ℹ️ Использование: /createcoin[ТИКЕР] [Название]\n<i>Цена будет выдана случайно от 100 до 500.</i>")
    except Exception as e: 
        logging.error(f"Ошибка создания монеты: {e}")

@router.message(Command("cr_send"))
async def cmd_cr_send(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if await check_ban(chat_id, user_id):
        return
        
    if not message.reply_to_message: 
        return
        
    args = message.text.split()
    if len(args) < 3: 
        return await message.answer("ℹ️ Использование: /cr_send [ТИКЕР][Сумма]")
        
    ticker = args[1].upper()
    try:
        amount = int(args[2])
        if amount <= 0: 
            return await message.answer("❌ Сумма перевода должна быть больше 0.")
    except ValueError: 
        return await message.answer("❌ Сумма должна быть числом.")
        
    coin_id = ticker.lower()
    from user_manager import get_user_data, update_user_field
    
    ud = await get_user_data(chat_id, user_id)
    if not ud: ud = {}
    port = ud.get('crypto_portfolio', {})
    
    if port.get(coin_id, 0) < amount: 
        return await message.answer(f"❌ На вашем балансе недостаточно {ticker}.")
        
    port[coin_id] -= amount
    if port[coin_id] <= 0: 
        del port[coin_id]
    
    tax = max(1, int(amount * 0.10)) # Налог 10% на P2P перевод (хардкор)
    final = amount - tax
    
    target_id = message.reply_to_message.from_user.id
    rd = await get_user_data(chat_id, target_id)
    if not rd: rd = {}
    r_port = rd.get('crypto_portfolio', {})
    
    r_port[coin_id] = r_port.get(coin_id, 0) + final
    
    await update_user_field(chat_id, user_id, 'crypto_portfolio', port)
    await update_user_field(chat_id, target_id, 'crypto_portfolio', r_port)
    
    await message.answer(f"💸 Перевод завершен! Получено: <b>{fmt(final)}</b> {ticker} (налог 10%).")

# ============================================================================
# БЛОК 6: ИНТЕРФЕЙС И КНОПКИ (С REAL-TIME ЭФФЕКТОМ)
# ============================================================================

def get_crypto_main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📈 Состояние рынка", callback_data="crypto_market")
    builder.button(text="💼 Мой портфель", callback_data="crypto_portfolio")
    builder.button(text="🪙 Листинг монеты", callback_data="crypto_create")
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("криптосыроежка"))
async def cmd_crypto_main(message: types.Message):
    if await check_ban(message.chat.id, message.from_user.id): 
        return
        
    await message.answer("📊 <b>SYROEZHKA CRYPTO EXCHANGE</b>\n\nВыбери раздел:", reply_markup=get_crypto_main_kb())

@router.callback_query(F.data == "crypto_main")
async def cb_crypto_main(callback: types.CallbackQuery):
    await callback.answer()
    await smart_edit(callback, "📊 <b>SYROEZHKA CRYPTO EXCHANGE</b>\n\nГлавное меню.", get_crypto_main_kb())

@router.callback_query(F.data == "crypto_market")
async def cb_crypto_market(callback: types.CallbackQuery):
    await callback.answer()
    coins = await get_all_coins()
    
    builder = InlineKeyboardBuilder()
    text = "📊 <b>ТЕКУЩИЕ КОТИРОВКИ</b>\n\n"
    
    if not coins: 
        text += "Рынок пуст. Станьте первым, кто выпустит монету!"
        
    for cid, coin in coins.items():
        curr = coin["prices"][-1]
        prev = coin["prices"][-2] if len(coin["prices"]) > 1 else curr
        emoji = "🚀" if curr >= prev else "🩸"
        text += f"<b>{coin['ticker']}</b>: {fmt(curr)} сыр. {emoji}\n"
        builder.button(text=f"{coin['ticker']} | {fmt(curr)}", callback_data=f"cr_view_{cid}")
        
    builder.button(text="📉 Общий индекс", callback_data="crypto_global_chart")
    builder.button(text="⬅️ Назад", callback_data="crypto_main")
    builder.adjust(1)
    
    await smart_edit(callback, text, builder.as_markup())

@router.callback_query(F.data == "crypto_global_chart")
async def cb_global_chart(callback: types.CallbackQuery):
    await callback.answer()
    coins = await get_all_coins()
    
    await callback.message.delete()
    load = await callback.message.answer("⏳ <i>Генерация индекса...</i>")
    
    chart_bytes = await generate_global_chart_async(coins)
    chart = BufferedInputFile(chart_bytes, filename="global.png")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К списку монет", callback_data="crypto_market")
    
    await load.delete()
    await callback.message.answer_photo(photo=chart, caption="🌐 <b>Глобальное состояние рынка</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("cr_view_"))
async def cb_coin_view(callback: types.CallbackQuery):
    """
    REAL-TIME ОБНОВЛЕНИЕ ГРАФИКА:
    Если график уже открыт, мы не пересоздаем сообщение, а бесшовно меняем картинку (edit_media).
    """
    cid = callback.data.replace("cr_view_", "")
    coins = await get_all_coins()
    
    if cid not in coins: 
        return await callback.answer("❌ Монета не найдена или была удалена.")
        
    coin = coins[cid]
    chart_bytes = await generate_chart_async(coin['name'], coin["prices"])
    chart = BufferedInputFile(chart_bytes, filename=f"{cid}.png")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Купить (Все) 📈", callback_data=f"cr_do_buy_all_{cid}")
    builder.button(text="Купить (10 шт) 📈", callback_data=f"cr_do_buy_10_{cid}")
    builder.button(text="Продать (Все) 📉", callback_data=f"cr_do_sell_all_{cid}")
    builder.button(text="Продать (10 шт) 📉", callback_data=f"cr_do_sell_10_{cid}")
    
    # Кнопка для Real-time обновления
    builder.button(text="🔄 Обновить график", callback_data=f"cr_view_{cid}")
    builder.button(text="⬅️ Назад", callback_data="crypto_market")
    
    builder.adjust(2, 2, 1, 1)
    caption = f"💰 <b>{coin['name']} ({coin['ticker']})</b>\n\nТекущий курс: <b>{fmt(coin['prices'][-1])}</b> сыр.\n<i>(Рынок обновляется раз в 10 минут)</i>"
    
    # БЕСШОВНОЕ ОБНОВЛЕНИЕ (Real-Time эффект без мерцания)
    if callback.message.photo:
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(media=chart, caption=caption, parse_mode="HTML"),
                reply_markup=builder.as_markup()
            )
            await callback.answer("✅ График обновлен!")
        except Exception:
            await callback.answer("График актуален", show_alert=False)
    else:
        # Если перешли из текста, удаляем старое и шлем картинку первый раз
        await callback.message.delete()
        load = await callback.message.answer(f"⏳ <i>Отрисовка {coin['ticker']}...</i>")
        await load.delete()
        await callback.message.answer_photo(photo=chart, caption=caption, reply_markup=builder.as_markup())
        await callback.answer()

@router.callback_query(F.data.startswith("cr_do_"))
async def cb_trade_execute(callback: types.CallbackQuery):
    """
    ТОРГОВЛЯ ТЕПЕРЬ НЕ ВЛИЯЕТ НА ГРАФИК!
    Игроки просто покупают или продают по текущей (сгенерированной ботом) цене.
    """
    if await check_ban(callback.message.chat.id, callback.from_user.id): 
        return await callback.answer("❌ Вы забанены на криптобирже.", show_alert=True)
        
    parts = callback.data.split("_", 4) 
    if len(parts) < 5: 
        return await callback.answer("❌ Ошибка данных.")
        
    action = parts[2]
    qty_str = parts[3]
    cid = parts[4]
    
    # get_all_coins УЖЕ просимулировал рынок на текущую секунду.
    # Так что цена свежайшая, и действия игрока на нее не влияют.
    coins = await get_all_coins()
    if cid not in coins: 
        return await callback.answer("❌ Монета не найдена.")
        
    coin = coins[cid]
    price = coin["prices"][-1]
    
    from user_manager import get_user_data, update_user_balance, update_user_field
    ud = await get_user_data(callback.message.chat.id, callback.from_user.id)
    if not ud: ud = {}
    port = ud.get('crypto_portfolio', {})
    user_balance = ud.get('balance', 0)
    
    if action == "buy":
        amount = user_balance // price if qty_str == "all" else int(qty_str)
        if amount <= 0:
            return await callback.answer("❌ Недостаточно средств для покупки.", show_alert=True)
            
        if user_balance < price * amount: 
            return await callback.answer("❌ Мало денег для такого количества.", show_alert=True)
            
        await update_user_balance(callback.message.chat.id, callback.from_user.id, -(price * amount))
        port[cid] = port.get(cid, 0) + amount
        
        await callback.answer(f"✅ Успешно куплено {amount} шт. {coin['ticker']}!")
        
    elif action == "sell":
        amount = port.get(cid, 0) if qty_str == "all" else int(qty_str)
        
        if amount <= 0:
            return await callback.answer("❌ У вас нет этой монеты для продажи.", show_alert=True)
            
        if port.get(cid, 0) < amount: 
            return await callback.answer("❌ Недостаточно монет в портфеле.", show_alert=True)
            
        # ХАРДКОР: Комиссия при продаже ТЕПЕРЬ 10% (заработать ОЧЕНЬ сложно)
        profit = int(price * amount * 0.90)
        await update_user_balance(callback.message.chat.id, callback.from_user.id, profit)
        
        port[cid] -= amount
        if port[cid] <= 0: 
            del port[cid]
            
        await callback.answer(f"✅ Успешно продано {amount} шт. {coin['ticker']}!")
        
    else: 
        return
    
    await update_user_field(callback.message.chat.id, callback.from_user.id, 'crypto_portfolio', port)
    
    # Возвращаемся в cb_coin_view, чтобы картинка обновилась БЕСШОВНО (edit_media)
    callback.data = f"cr_view_{cid}"
    await cb_coin_view(callback)

@router.callback_query(F.data == "crypto_portfolio")
async def cb_portfolio(callback: types.CallbackQuery):
    """Бронебойный портфель, который не крашится при битых данных."""
    await callback.answer()
    
    from user_manager import get_user_data
    ud = await get_user_data(callback.message.chat.id, callback.from_user.id)
    
    if not ud: ud = {}
    port = ud.get('crypto_portfolio', {})
    if not isinstance(port, dict): port = {}
    
    coins = await get_all_coins()
    
    text = "💼 <b>ВАШ ПОРТФЕЛЬ</b>\n\n"
    total = 0
    
    if not port:
        text += "<i>Ваш крипто-портфель пока пуст.</i>\n"
    else:
        for cid, qty in port.items():
            if cid in coins:
                val = qty * coins[cid]["prices"][-1]
                total += val
                text += f"▪️ <b>{coins[cid]['ticker']}</b>: {fmt(qty)} шт. (≈ {fmt(val)} сыр.)\n"
                
    text += f"\n💰 Общая стоимость портфеля: <b>{fmt(total)}</b> сыр."
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="crypto_main")
    
    await smart_edit(callback, text, builder.as_markup())

@router.callback_query(F.data == "crypto_create")
async def cb_create_info(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "🪙 <b>ЛИСТИНГ НОВОЙ МОНЕТЫ</b>\n\n"
        "Листинг на бирже теперь абсолютно <b>БЕСПЛАТЕН</b> (0 сыр)!\n"
        "<i>Лимит: 1 человек может запустить максимум 2 свои монеты.</i>\n\n"
        "<b>Как запустить монету:</b>\n"
        "<code>/createcoin [ТИКЕР] [Название]</code>\n"
        "<i>Пример: /createcoin DOGE Собачья Монета</i>\n"
        "(Цена будет выдана случайно от 100 до 500 сыр)"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="crypto_main")
    
    await smart_edit(callback, text, builder.as_markup())