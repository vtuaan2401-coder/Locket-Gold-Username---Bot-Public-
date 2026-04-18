import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update admin_menu
content = content.replace(
    '[KeyboardButton(text="💎 Cộng Số Dư")],',
    '[KeyboardButton(text="💎 Cộng Số Dư"), KeyboardButton(text="➖ Trừ Số Dư")],'
)

# 2. Add to KNOWN_BUTTONS
content = content.replace(
    '"💎 Cộng Số Dư", "⚙️ Setup Giá"',
    '"💎 Cộng Số Dư", "➖ Trừ Số Dư", "⚙️ Setup Giá"'
)

# 3. Update ADMIN BUTTONS block
admin_trigger = '''
        if text == "💎 Cộng Số Dư":
            state_store[user_id] = {"action": "await_admin_add_balance_target"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram cần cộng số dư:", reply_markup=select_all_users_menu(data))
            return
        if text == "➖ Trừ Số Dư":
            state_store[user_id] = {"action": "await_admin_sub_balance_target"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram cần trừ số dư:", reply_markup=select_all_users_menu(data))
            return
'''
content = content.replace(
    '        if text == "💎 Cộng Số Dư":\n            state_store[user_id] = {"action": "await_admin_add_balance_target"}\n            await message.answer("📝 Chọn hoặc nhập ID Telegram cần cộng số dư:", reply_markup=select_all_users_menu(data))\n            return',
    admin_trigger.strip()
)

# 4. Update STATE FLOW
state_flow_addition = '''
        if action == "await_admin_sub_balance_target":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            if not get_user(data, uid):
                await message.answer("⚠️ Không tìm thấy người dùng.")
                return
            state_store[user_id] = {"action": "await_admin_sub_balance_amount", "target_id": uid}
            await message.answer("📝 Nhập số 💎 muốn trừ:", reply_markup=cancel_only_menu())
            return

        if action == "await_admin_sub_balance_amount":
            amount = parse_positive_int(text)
            if amount is None:
                await message.answer("❌ Số dư phải là số.")
                return
            target_id = state["target_id"]
            ok, reason = deduct_balance(data, target_id, amount)
            if ok:
                save_data(data)
                await message.answer(f"✅ Đã trừ {amount}💎 của ID {target_id}.", reply_markup=role_menu(data, user_id))
            else:
                await message.answer(f"❌ {reason}", reply_markup=role_menu(data, user_id))
            del state_store[user_id]
            return
'''

content = content.replace(
    '        if action == "await_admin_add_balance_amount":',
    state_flow_addition.lstrip() + '\n        if action == "await_admin_add_balance_amount":'
)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Added subtract balance feature successfully!")
