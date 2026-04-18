import os

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add parse_user_id
content = content.replace(
    '    return int(text)\n',
    '    return int(text)\n\n\ndef parse_user_id(text: str) -> Optional[int]:\n    text = (text or "").strip()\n    if text.startswith("🆔 "): \n        text = text.split(" - ")[0].replace("🆔 ", "").strip()\n    if not text.isdigit():\n        return None\n    return int(text)\n', 1)

# 2. Add Menus
menus_code = '''
def cancel_only_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Quay Lại")]],
        resize_keyboard=True,
    )

def select_agent_menu(data: dict) -> ReplyKeyboardMarkup:
    keyboard = []
    for uid, info in data["users"].items():
        if info["role"] == "agent":
            keyboard.append([KeyboardButton(text=f"🆔 {uid} - {info['name']}")])
    keyboard.append([KeyboardButton(text="⬅️ Quay Lại")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def select_ctv_menu(data: dict, parent_id: Optional[int] = None) -> ReplyKeyboardMarkup:
    keyboard = []
    for uid, info in data["users"].items():
        if info["role"] == "collaborator":
            if parent_id is None or info.get("parent_id") == str(parent_id):
                keyboard.append([KeyboardButton(text=f"🆔 {uid} - {info['name']}")])
    keyboard.append([KeyboardButton(text="⬅️ Quay Lại")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def select_all_users_menu(data: dict) -> ReplyKeyboardMarkup:
    keyboard = []
    for uid, info in data["users"].items():
        if info["role"] != "admin":
            keyboard.append([KeyboardButton(text=f"🆔 {uid} - {info['name']}")])
    keyboard.append([KeyboardButton(text="⬅️ Quay Lại")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

'''
content = content.replace('# =========================\n# START', menus_code + '# =========================\n# START', 1)

# 3. Update Admin Actions
content = content.replace('await message.answer("📝 Nhập ID Telegram Đại Lý cần xóa:")', 'await message.answer("📝 Chọn hoặc nhập ID Telegram Đại Lý cần xóa:", reply_markup=select_agent_menu(data))')
content = content.replace('await message.answer("📝 Nhập ID Telegram CTV cần xóa:")', 'await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần xóa:", reply_markup=select_ctv_menu(data))')
content = content.replace('await message.answer("📝 Nhập ID Telegram cần cộng số dư:")', 'await message.answer("📝 Chọn hoặc nhập ID Telegram cần cộng số dư:", reply_markup=select_all_users_menu(data))')
content = content.replace('await message.answer("📝 Nhập ID Telegram cần setup giá riêng:")', 'await message.answer("📝 Chọn hoặc nhập ID Telegram cần setup giá riêng:", reply_markup=select_all_users_menu(data))')

# 4. Update Agent Actions
content = content.replace('await message.answer("📝 Nhập ID Telegram CTV cần xóa:")', 'await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần xóa:", reply_markup=select_ctv_menu(data, user_id))')
content = content.replace('await message.answer("📝 Nhập ID Telegram CTV cần cộng số dư:")', 'await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần cộng số dư:", reply_markup=select_ctv_menu(data, user_id))')
content = content.replace('await message.answer("📝 Nhập ID Telegram CTV cần setup giá gói 3s:")', 'await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần setup giá gói 3s:", reply_markup=select_ctv_menu(data, user_id))')
content = content.replace('await message.answer("📝 Nhập ID Telegram CTV cần setup giá gói 15s:")', 'await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần setup giá gói 15s:", reply_markup=select_ctv_menu(data, user_id))')

# 5. Update parse_user_id and cancel_only_menu in State Flow
# Use parse_user_id for all uid parsing
content = content.replace('uid = parse_positive_int(text)', 'uid = parse_user_id(text)')

# Update reply_markup for intermediate steps
content = content.replace('await message.answer("📝 Nhập tên cho Đại Lý:")', 'await message.answer("📝 Nhập tên cho Đại Lý:", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("📝 Nhập tên cho CTV:")', 'await message.answer("📝 Nhập tên cho CTV:", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("📝 Nhập số 💎 muốn cộng:")', 'await message.answer("📝 Nhập số 💎 muốn cộng:", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("📝 Nhập số 💎 muốn cộng cho CTV:")', 'await message.answer("📝 Nhập số 💎 muốn cộng cho CTV:", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("👉 Nhập 1 cho gói 3s hoặc 2 cho gói 15s")', 'await message.answer("👉 Nhập 1 cho gói 3s hoặc 2 cho gói 15s", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("📝 Nhập giá muốn setup:")', 'await message.answer("📝 Nhập giá muốn setup:", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("📝 Nhập giá muốn setup cho CTV:")', 'await message.answer("📝 Nhập giá muốn setup cho CTV:", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("📝 Nhập giá mới cho gói 3s:")', 'await message.answer("📝 Nhập giá mới cho gói 3s:", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("📝 Nhập giá mới cho gói 15s:")', 'await message.answer("📝 Nhập giá mới cho gói 15s:", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("📝 Nhập ID Telegram Đại Lý:")', 'await message.answer("📝 Nhập ID Telegram Đại Lý:", reply_markup=cancel_only_menu())')
content = content.replace('await message.answer("📝 Nhập ID Telegram CTV:")', 'await message.answer("📝 Nhập ID Telegram CTV:", reply_markup=cancel_only_menu())')

# 6. Add role_menu back after success
def add_role_menu(msg, c):
    return c.replace(f'await message.answer(\\n                    {msg}\\n                )', f'await message.answer(\\n                    {msg},\\n                    reply_markup=role_menu(data, user_id)\\n                )').replace(f'await message.answer({msg})', f'await message.answer({msg}, reply_markup=role_menu(data, user_id))')

content = add_role_menu('f"✅ Đã cấp quyền Đại Lý\\n🆔 ID: {target_id}\\n👤 Tên: {target_name}"', content)
content = add_role_menu('f"✅ Đã cấp quyền CTV\\n🆔 ID: {target_id}\\n👤 Tên: {target_name}"', content)
content = add_role_menu('f"✅ Đã thêm CTV\\n🆔 ID: {target_id}\\n👤 Tên: {target_name}"', content)
content = add_role_menu('f"✅ Đã xóa Đại Lý ID {uid}."', content)
content = add_role_menu('f"✅ Đã xóa CTV ID {uid}."', content)
content = add_role_menu('f"✅ Đã cộng {amount}💎 cho ID {target_id}."', content)
content = add_role_menu('f"✅ Đã cộng {amount}💎 cho CTV ID {target_id}."', content)
content = add_role_menu('f"✅ Đã setup giá gói 3s = {amount}💎"', content)
content = add_role_menu('f"✅ Đã setup giá gói 15s = {amount}💎"', content)
content = add_role_menu('f"✅ Đã set giá riêng cho ID {target_id}\\n{package_label(package_key)} = {amount}💎"', content)
content = add_role_menu('f"✅ Đã set giá cho CTV ID {target_id}\\n{package_label(package_key)} = {amount}💎"', content)

# 7. Update get_last_orders_for_user for the new history logic
new_history_logic = """
def get_last_orders_for_user(data: dict, user_id: int, limit: int = 10) -> list:
    user = get_user(data, user_id)
    if not user:
        return []
    
    if user["role"] == "admin":
        rows = data["orders"]
    elif user["role"] == "agent":
        # Agent sees their own and their CTVs
        rows = [x for x in data["orders"] if x["operator_id"] == user_id or (get_user(data, x["operator_id"]) and get_user(data, x["operator_id"])["parent_id"] == str(user_id))]
    else:
        # CTV sees only theirs
        rows = [x for x in data["orders"] if x["operator_id"] == user_id]
        
    return rows[-limit:]
"""
# Replace the existing function
import re
content = re.sub(r'def get_last_orders_for_user\(data: dict, user_id: int, limit: int = 10\) -> list:.*?return rows\[-limit:\]', new_history_logic.strip(), content, flags=re.DOTALL)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Bot updated successfully!")
