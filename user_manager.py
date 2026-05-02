import time
import asyncio
import secrets
from db import get_db

def get_user_ref(chat_id, user_id):
    db = get_db()
    return db.collection('chats').document(str(chat_id)).collection('users').document(str(user_id))

# Кэш пользователей
_user_cache = {}
CACHE_TTL = 10.0 

def get_from_cache(chat_id, user_id):
    key = (chat_id, user_id)
    if key in _user_cache:
        cache_entry = _user_cache[key]
        if time.time() - cache_entry["timestamp"] < CACHE_TTL:
            return cache_entry["data"].copy()
    return None

def set_in_cache(chat_id, user_id, data):
    key = (chat_id, user_id)
    _user_cache[key] = {"data": data.copy(), "timestamp": time.time()}

async def get_user_data(chat_id, user_id, full_name=None):
    cached_data = get_from_cache(chat_id, user_id)
    if cached_data:
        if full_name and cached_data.get('full_name') != full_name:
            cached_data['full_name'] = full_name
            set_in_cache(chat_id, user_id, cached_data)
            ref = get_user_ref(chat_id, user_id)
            asyncio.create_task(ref.update({'full_name': full_name}))
        return cached_data

    ref = get_user_ref(chat_id, user_id)
    doc = await ref.get()

    if doc.exists:
        data = doc.to_dict()
        if full_name and data.get('full_name') != full_name:
            await ref.update({'full_name': full_name})
            data['full_name'] = full_name
        set_in_cache(chat_id, user_id, data)
        return data
    else:
        default_name = full_name if full_name else "Игрок"
        default_data = {
            'balance': 500,
            'bank_deposit': 0,
            'bank_name': None, # Название банка, где открыт счет
            'last_bonus_time': 0,
            'last_daily_time': 0,
            'last_work_time': 0,
            'last_crime_time': 0,
            'inventory': {},
            'warns':[],
            'is_banned': False,
            'hide_in_top': False,
            'full_name': default_name,
            'is_vip': False,
            'is_banker': False, # НОВАЯ РОЛЬ БАНКИРА
            'debts': {},
            'escort_count': 0
        }
        await ref.set(default_data)
        set_in_cache(chat_id, user_id, default_data)
        return default_data

async def update_user_balance(chat_id, user_id, amount, is_debt_repayment=False):
    ref = get_user_ref(chat_id, user_id)
    data = await get_user_data(chat_id, user_id)
    
    new_balance = data.get('balance', 0) + amount
    await ref.update({'balance': new_balance})

    data['balance'] = new_balance
    set_in_cache(chat_id, user_id, data)
    return new_balance

async def update_user_field(chat_id, user_id, field, value):
    ref = get_user_ref(chat_id, user_id)
    await ref.update({field: value})
    
    data = await get_user_data(chat_id, user_id)
    data[field] = value
    set_in_cache(chat_id, user_id, data)

async def check_and_give_bonus(chat_id, user_id, full_name=None):
    data = await get_user_data(chat_id, user_id, full_name)
    if data.get('is_banned', False):
        return False, {}

    current_time = time.time()
    
    last_bonus = data.get('last_bonus_time', 0)

    if current_time - last_bonus >= 3600:
        bank_deposit = data.get('bank_deposit', 0)
        bank_income = 0
        is_daily = False

        # ФИКСИРОВАННЫЙ БОНУС ДЛЯ ВСЕХ (без налогов на эту сумму)
        base_bonus = 1000 

        # Ежедневные проверки (проценты по старым системным вкладам, не привязанным к банкам)
        if current_time - data.get('last_daily_time', 0) >= 79200:
            is_daily = True
            if bank_deposit > 0 and not data.get('bank_name'):
                if bank_deposit <= 100000000: bank_income = int(bank_deposit * 0.01)
                elif bank_deposit <= 1000000000: bank_income = int(bank_deposit * 0.005)
                else: bank_income = int(bank_deposit * 0.002)

        from shop import ITEMS
        from economy_utils import get_global_tax

        tax_percent = await get_global_tax()
        neg_lvl = data.get('skills', {}).get('negotiation', 0)
        tax_percent = max(0, tax_percent - neg_lvl)

        biz_income = 0
        car_income = 0
        inventory = data.get('inventory', {})

        for item_id, count in inventory.items():
            item = ITEMS.get(item_id)
            if not item: continue
            if item.get('action') == 'business':
                biz_income += item.get('income', 0) * min(count, 10)
            elif item.get('action') == 'car':
                car_income += item.get('income', 0) * count

        if data.get('is_banker', False):
            # Доходы банкиров от бизнесов и машин урезаны до 10%
            biz_income = int(biz_income * 0.1)
            car_income = int(car_income * 0.1)

        extra_income = biz_income + car_income + bank_income
        tax_amt = int(extra_income * (tax_percent / 100.0))
        total_to_hand = base_bonus + extra_income - tax_amt

        if total_to_hand <= 0: return False, {}

        ref = get_user_ref(chat_id, user_id)
        upd = {
            'balance': data.get('balance', 0) + total_to_hand,
            'last_bonus_time': current_time
        }
        if is_daily:
            upd['last_daily_time'] = current_time
            if bank_deposit > 0 and not data.get('bank_name'):
                upd['bank_deposit'] = bank_deposit + bank_income

        await ref.update(upd)
        data.update(upd)
        set_in_cache(chat_id, user_id, data)

        return True, {
            'base': base_bonus, 'business': biz_income, 'car': car_income,
            'tax_percent': tax_percent, 'tax_amount': tax_amt, 'total': total_to_hand,
            'is_banker_bonus': False
        }
    return False, {}

async def add_item_to_inventory(chat_id, user_id, item_name):
    ref = get_user_ref(chat_id, user_id)
    data = await get_user_data(chat_id, user_id)
    inv = data.get('inventory', {})
    inv[item_name] = inv.get(item_name, 0) + 1
    await ref.update({'inventory': inv})
    data['inventory'] = inv
    set_in_cache(chat_id, user_id, data)

async def remove_item_from_inventory(chat_id, user_id, item_name):
    ref = get_user_ref(chat_id, user_id)
    data = await get_user_data(chat_id, user_id)
    inv = data.get('inventory', {})
    if inv.get(item_name, 0) > 0:
        inv[item_name] -= 1
        if inv[item_name] <= 0: del inv[item_name]
        await ref.update({'inventory': inv})
        data['inventory'] = inv
        set_in_cache(chat_id, user_id, data)
        return True
    return False

async def get_top_users(chat_id, limit=10):
    db = get_db()
    ref = db.collection('chats').document(str(chat_id)).collection('users')
    docs = await ref.order_by('balance', direction='DESCENDING').limit(limit + 10).get()
    
    users =[]
    for doc in docs:
        data = doc.to_dict()
        if not data.get('hide_in_top', False) and not data.get('is_banned', False):
            users.append({'user_id': doc.id, **data})
        if len(users) >= limit:
            break
            
    return users

async def is_user_banker(chat_id, user_id):
    data = await get_user_data(chat_id, user_id)
    return data.get('is_banker', False)

async def get_all_users_in_chat(chat_id):
    db = get_db()
    ref = db.collection('chats').document(str(chat_id)).collection('users')
    docs = await ref.get()
    return docs