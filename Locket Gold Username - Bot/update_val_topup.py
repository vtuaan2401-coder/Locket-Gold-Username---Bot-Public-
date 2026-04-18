import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
content = content.replace(
    'from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile',
    'from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery'
)

# 2. Add validation helper
validation_helper = '''
async def validate_user_id(bot, message, uid):
    try:
        await bot.get_chat(uid)
        return True
    except Exception:
        await message.answer("❌ ID này không hợp lệ hoặc người dùng chưa từng tương tác với bot.\\nVui lòng yêu cầu họ ấn /start trước.")
        return False
'''

# Insert it before STATE FLOW
content = content.replace('# =========================\n    # STATE FLOW', validation_helper + '\n    # =========================\n    # STATE FLOW')

# 3. Add validation calls
content = content.replace(
    'if uid is None:\n                await message.answer("❌ ID Telegram phải là số.")\n                return\n            state_store[user_id] = {"action": "await_add_agent_name", "target_id": uid}',
    'if uid is None:\n                await message.answer("❌ ID Telegram phải là số.")\n                return\n            if not await validate_user_id(bot, message, uid):\n                return\n            state_store[user_id] = {"action": "await_add_agent_name", "target_id": uid}'
)

content = content.replace(
    'if uid is None:\n                await message.answer("❌ ID Telegram phải là số.")\n                return\n            state_store[user_id] = {"action": "await_add_ctv_admin_name", "target_id": uid}',
    'if uid is None:\n                await message.answer("❌ ID Telegram phải là số.")\n                return\n            if not await validate_user_id(bot, message, uid):\n                return\n            state_store[user_id] = {"action": "await_add_ctv_admin_name", "target_id": uid}'
)

content = content.replace(
    'if uid is None:\n                await message.answer("❌ ID Telegram phải là số.")\n                return\n            state_store[user_id] = {"action": "await_agent_add_ctv_name", "target_id": uid}',
    'if uid is None:\n                await message.answer("❌ ID Telegram phải là số.")\n                return\n            if not await validate_user_id(bot, message, uid):\n                return\n            state_store[user_id] = {"action": "await_agent_add_ctv_name", "target_id": uid}'
)

# 4. Update topup confirm for Admin
admin_topup_notify = '''
            try:
                topup_markup = InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(
                            text="✅ Duyệt Nạp", 
                            callback_data=f"approve_topup_{user_id}_{amount}"
                        )
                    ]]
                )
                await bot.send_message(
                    ADMIN_ID,
                    "🔔 Có yêu cầu nạp tiền mới\\n"
                    f"🆔 ID: {user_id}\\n"
                    f"👤 Tên: {requester['name']}\\n"
                    f"🏷 Vai trò: {requester['role']}\\n"
                    f"💎 Số lượng: {amount}\\n"
                    f"🕒 {now_str()}",
                    reply_markup=topup_markup
                )
'''
old_admin_notify = '''
            try:
                await bot.send_message(
                    ADMIN_ID,
                    "🔔 Có yêu cầu nạp tiền mới\\n"
                    f"🆔 ID: {user_id}\\n"
                    f"👤 Tên: {requester['name']}\\n"
                    f"🏷 Vai trò: {requester['role']}\\n"
                    f"💎 Số lượng: {amount}\\n"
                    f"🕒 {now_str()}",
                )
'''
content = content.replace(old_admin_notify.strip(), admin_topup_notify.strip())

# 5. Add callback query handler at the end of the file, before main()
callback_handler = '''
@dp.callback_query(lambda c: c.data and c.data.startswith('approve_topup_'))
async def process_approve_topup(callback_query: CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Bạn không có quyền này.", show_alert=True)
        return

    data_parts = callback_query.data.split('_')
    if len(data_parts) != 4:
        return
    
    target_id = int(data_parts[2])
    amount = int(data_parts[3])

    data = load_data()
    target_user = get_user(data, target_id)

    if not target_user:
        await callback_query.answer("❌ Người dùng không còn tồn tại.", show_alert=True)
        return

    # Check if already approved by checking message text
    if "✅ Đã Duyệt" in callback_query.message.text:
        await callback_query.answer("❌ Đơn này đã được duyệt rồi.", show_alert=True)
        return

    # Add balance
    add_balance(data, target_id, amount)
    
    # Update pending_topups status
    for req in data.get("pending_topups", []):
        if req["user_id"] == target_id and req["amount"] == amount and req["status"] == "pending":
            req["status"] = "approved"
            break
            
    save_data(data)

    try:
        await bot.send_message(
            target_id, 
            f"✅ Yêu cầu nạp {amount}💎 của bạn đã được Admin duyệt thành công!"
        )
    except Exception:
        pass
    
    new_text = callback_query.message.text + "\\n\\n✅ Đã Duyệt!"
    await callback_query.message.edit_text(new_text)
    await callback_query.answer("✅ Đã cộng tiền thành công!")

'''
content = content.replace('async def main():', callback_handler + '\nasync def main():')

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("bot.py updated!")
