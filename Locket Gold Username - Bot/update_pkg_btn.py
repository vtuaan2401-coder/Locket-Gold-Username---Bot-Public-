import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add package_type_menu()
package_type_menu_code = '''
def package_type_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Gói 3s"), KeyboardButton(text="Gói 15s")],
            [KeyboardButton(text="⬅️ Quay Lại")],
        ],
        resize_keyboard=True,
    )
'''
content = content.replace(
    'def permission_menu() -> ReplyKeyboardMarkup:',
    package_type_menu_code.lstrip() + '\n\ndef permission_menu() -> ReplyKeyboardMarkup:'
)

# 2. Update await_admin_custom_price_target response
content = content.replace(
    'await message.answer("👉 Nhập 1 cho gói 3s hoặc 2 cho gói 15s", reply_markup=cancel_only_menu())',
    'await message.answer("👉 Chọn gói 3s hoặc 15s:", reply_markup=package_type_menu())'
)

# 3. Update await_admin_custom_price_package logic
old_logic = '''
        if action == "await_admin_custom_price_package":
            if text not in ["1", "2"]:
                await message.answer("❌ Nhập 1 hoặc 2.")
                return
            package_key = "package_3s" if text == "1" else "package_15s"
'''
new_logic = '''
        if action == "await_admin_custom_price_package":
            if text not in ["Gói 3s", "Gói 15s"]:
                await message.answer("❌ Chọn Gói 3s hoặc Gói 15s.")
                return
            package_key = "package_3s" if text == "Gói 3s" else "package_15s"
'''
content = content.replace(old_logic.strip(), new_logic.strip())

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated custom price user menu to use buttons!")
