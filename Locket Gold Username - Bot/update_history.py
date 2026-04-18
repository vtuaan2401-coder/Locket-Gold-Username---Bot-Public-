import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update "Lịch Sử Đơn"
old_history = '''
        await message.answer("\\n\\n".join(lines))
        return
'''
new_history = '''
        if is_admin(user_id):
            history_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🗑 Xóa toàn bộ lịch sử", callback_data="delete_history_all")],
                    [InlineKeyboardButton(text="🗑 Xóa lịch sử theo ID", callback_data="delete_history_user")]
                ]
            )
            await message.answer("\\n\\n".join(lines), reply_markup=history_markup)
        else:
            await message.answer("\\n\\n".join(lines))
        return
'''
content = content.replace(old_history, new_history)

# 2. Add state flow for await_admin_delete_history_target
state_handler = '''
        if action == "await_admin_delete_history_target":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            if not get_user(data, uid):
                await message.answer("⚠️ Không tìm thấy người dùng.")
                return
            
            # Xóa đơn của người này
            original_len = len(data.get("orders", []))
            data["orders"] = [order for order in data.get("orders", []) if order.get("operator_id") != uid]
            save_data(data)
            
            deleted_count = original_len - len(data["orders"])
            await message.answer(f"✅ Đã xóa {deleted_count} đơn hàng của ID {uid}.", reply_markup=role_menu(data, user_id))
            del state_store[user_id]
            return
'''

content = content.replace(
    '        if action == "await_admin_custom_price_target":',
    state_handler.lstrip() + '\n        if action == "await_admin_custom_price_target":'
)

# 3. Add Callback handlers for history
callback_history = '''
@dp.callback_query(lambda c: c.data == 'delete_history_all')
async def process_delete_history_all(callback_query: CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Bạn không có quyền này.", show_alert=True)
        return
        
    data = load_data()
    data["orders"] = []
    save_data(data)
    
    await callback_query.message.edit_text("✅ Toàn bộ lịch sử đơn hàng đã bị xóa sạch.")
    await callback_query.answer("Đã xóa toàn bộ lịch sử!")

@dp.callback_query(lambda c: c.data == 'delete_history_user')
async def process_delete_history_user(callback_query: CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Bạn không có quyền này.", show_alert=True)
        return
        
    data = load_data()
    user_id = callback_query.from_user.id
    state_store[user_id] = {"action": "await_admin_delete_history_target"}
    
    await bot.send_message(
        user_id, 
        "📝 Chọn hoặc nhập ID Telegram để xóa lịch sử:", 
        reply_markup=select_all_users_menu(data)
    )
    await callback_query.answer()

'''

content = content.replace('async def main():', callback_history + '\nasync def main():')

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated history deletion for Admin!")
