import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import logging

logging.basicConfig(level=logging.INFO)

from config import BOT_TOKEN, ADMIN_ID, QR_IMAGE, DATA_FILE

# =========================
# NOTE
# =========================
# This bot is a SAFE business-management scaffold.
# It does NOT perform real Locket account checks or premium/gold upgrades.
# The functions `check_account_mock` and `create_order_mock` are placeholders.
# Replace them ONLY with APIs you are authorized to use.

if not BOT_TOKEN or BOT_TOKEN == "DAN_TOKEN_MOI_VAO_DAY":
    raise ValueError("Bạn chưa thay BOT_TOKEN trong config.py")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
state_store: Dict[int, Dict[str, Any]] = {}


# =========================
# DATA LAYER
# =========================
def default_data() -> dict:
    return {
        "users": {
            str(ADMIN_ID): {
                "role": "admin",
                "name": "Admin",
                "balance": 0,
                "parent_id": None,
            }
        },
        "prices": {
            "global": {
                "package_3s": 40,
                "package_15s": 60,
            },
            # admin custom price for any single user
            "admin_user_custom": {},
            # agent custom price for own collaborators
            # {agent_id: {ctv_id: {package_3s: 40, package_15s: 50}}}
            "agent_ctv_custom": {},
        },
        "orders": [],
        "pending_topups": [],
    }


def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        data = default_data()
        save_data(data)
        return data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = default_data()
        save_data(data)
    return data


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# HELPERS
# =========================
def now_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def format_dt(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def parse_positive_int(text: str) -> Optional[int]:
    text = (text or "").strip()
    if not text.isdigit():
        return None
    return int(text)


def parse_user_id(text: str) -> Optional[int]:
    text = (text or "").strip()
    if text.startswith("🆔 "): 
        text = text.split(" - ")[0].replace("🆔 ", "").strip()
    if not text.isdigit():
        return None
    return int(text)


def get_user(data: dict, user_id: int) -> Optional[dict]:
    return data["users"].get(str(user_id))


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def is_agent(data: dict, user_id: int) -> bool:
    user = get_user(data, user_id)
    return bool(user and user["role"] == "agent")


def is_collaborator(data: dict, user_id: int) -> bool:
    user = get_user(data, user_id)
    return bool(user and user["role"] == "collaborator")


def is_authorized(data: dict, user_id: int) -> bool:
    return str(user_id) in data["users"]


def role_text(role: str) -> str:
    if role == "admin":
        return "👑 Admin"
    if role == "agent":
        return "🏆 Đại Lý"
    if role == "collaborator":
        return "🏅 Cộng Tác Viên"
    return "🙋 Người Dùng"


def package_key_from_text(text: str) -> Optional[str]:
    if text == "📦 Locket Gold Username ( Quay Clip 3s )":
        return "package_3s"
    if text == "📦 Locket Gold Username ( Quay Clip 15s )":
        return "package_15s"
    return None


def package_label(package_key: str) -> str:
    if package_key == "package_3s":
        return "📦 Locket Gold Username ( Quay Clip 3s )"
    if package_key == "package_15s":
        return "📦 Locket Gold Username ( Quay Clip 15s )"
    return "📦 Gói Không Xác Định"


def get_effective_price(data: dict, buyer_id: int, package_key: str) -> Optional[int]:
    buyer = get_user(data, buyer_id)
    if not buyer:
        return None

    if buyer["role"] == "admin":
        return 0

    if buyer["role"] == "agent":
        # Agent must follow admin price (global or admin custom), not self-controlled
        custom = data["prices"]["admin_user_custom"].get(str(buyer_id), {})
        if package_key in custom:
            return custom[package_key]
        return data["prices"]["global"].get(package_key, 0)

    if buyer["role"] == "collaborator":
        parent_id = buyer.get("parent_id")
        # Agent custom price for own ctv first
        if parent_id:
            agent_custom = data["prices"]["agent_ctv_custom"].get(str(parent_id), {})
            ctv_custom = agent_custom.get(str(buyer_id), {})
            if package_key in ctv_custom:
                return ctv_custom[package_key]

        # admin custom for this user if exists
        admin_custom = data["prices"]["admin_user_custom"].get(str(buyer_id), {})
        if package_key in admin_custom:
            return admin_custom[package_key]

        return data["prices"]["global"].get(package_key, 0)

    return None


def add_balance(data: dict, user_id: int, amount: int) -> bool:
    user = get_user(data, user_id)
    if not user:
        return False
    user["balance"] += amount
    return True


def deduct_balance(data: dict, user_id: int, amount: int):
    user = get_user(data, user_id)
    if not user:
        return False, "Không tìm thấy người dùng."

    if user["role"] == "admin":
        return True, "Admin không bị trừ số dư."

    if user["balance"] < amount:
        return False, "Số dư không đủ."

    user["balance"] -= amount
    return True, "Đã trừ số dư."


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


def build_start_text(data: dict, user_id: int, full_name: str) -> str:
    user = get_user(data, user_id)
    if not user:
        return "❌ Bạn chưa được cấp quyền."

    if user["role"] == "admin":
        return f"👑 Admin\nXin Chào👋🏻 {full_name}"

    return (
        f"{role_text(user['role'])}: {user['name']}\n"
        f"Xin Chào👋🏻 {full_name}\n"
        f"Số Dư 💎: {user['balance']}"
    )


# =========================
# MOCK BUSINESS FLOW
# =========================
async def check_account_mock(username: str) -> dict:
    """
    Placeholder only. Replace with an API you are authorized to use.
    """
    username = username.strip()
    if not username or "fail" in username.lower():
        return {"ok": False}
    return {"ok": True, "display_name": username}


async def create_order_mock(username: str, package_key: str) -> dict:
    """
    Placeholder only. Replace with an API you are authorized to use.
    """
    checked = await check_account_mock(username)
    if not checked["ok"]:
        return {"ok": False}

    start_time = datetime.now()
    end_time = start_time + timedelta(days=30)
    return {
        "ok": True,
        "display_name": checked["display_name"],
        "start_time": format_dt(start_time),
        "end_time": format_dt(end_time),
    }


# =========================
# MENUS
# =========================
def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Up Locket Gold")],
            [KeyboardButton(text="💎 Cộng Số Dư"), KeyboardButton(text="➖ Trừ Số Dư")],
            [KeyboardButton(text="⚙️ Setup Giá")],
            [KeyboardButton(text="🔐 Cấp Quyền")],
            [KeyboardButton(text="💰 Xem Số Dư"), KeyboardButton(text="📜 Lịch Sử Đơn")],
        ],
        resize_keyboard=True,
    )


def agent_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Up Locket Gold")],
            [KeyboardButton(text="💎 Nạp"), KeyboardButton(text="💎 Cộng Số Dư CTV")],
            [KeyboardButton(text="⚙️ Setup Giá CTV")],
            [KeyboardButton(text="📋 Danh Sách Cộng Tác Viên")],
            [KeyboardButton(text="➕ Thêm CTV"), KeyboardButton(text="➖ Xóa CTV")],
            [KeyboardButton(text="💰 Xem Số Dư"), KeyboardButton(text="📜 Lịch Sử Đơn")],
        ],
        resize_keyboard=True,
    )


def collaborator_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Up Locket Gold")],
            [KeyboardButton(text="💎 Nạp")],
            [KeyboardButton(text="💰 Xem Số Dư"), KeyboardButton(text="📜 Lịch Sử Đơn")],
        ],
        resize_keyboard=True,
    )


def role_menu(data: dict, user_id: int) -> ReplyKeyboardMarkup:
    if is_admin(user_id):
        return admin_menu()
    if is_agent(data, user_id):
        return agent_menu()
    return collaborator_menu()


def package_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Locket Gold Username ( Quay Clip 3s )")],
            [KeyboardButton(text="📦 Locket Gold Username ( Quay Clip 15s )")],
            [KeyboardButton(text="⬅️ Quay Lại")],
        ],
        resize_keyboard=True,
    )


def package_type_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Gói 3s"), KeyboardButton(text="Gói 15s")],
            [KeyboardButton(text="⬅️ Quay Lại")],
        ],
        resize_keyboard=True,
    )


def permission_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Cấp Quyền Đại Lý")],
            [KeyboardButton(text="🏅 Cấp Quyền CTV")],
            [KeyboardButton(text="📋 Danh Sách Đại Lý"), KeyboardButton(text="📋 Danh Sách CTV Toàn Bộ")],
            [KeyboardButton(text="➖ Xóa Đại Lý"), KeyboardButton(text="➖ Xóa CTV")],
            [KeyboardButton(text="⬅️ Quay Lại")],
        ],
        resize_keyboard=True,
    )


def admin_price_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💵 Set Giá Gói 3s"), KeyboardButton(text="💵 Set Giá Gói 15s")],
            [KeyboardButton(text="🎯 Set Giá Riêng User")],
            [KeyboardButton(text="⬅️ Quay Lại")],
        ],
        resize_keyboard=True,
    )


def agent_price_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💵 Set Giá CTV Gói 3s"), KeyboardButton(text="💵 Set Giá CTV Gói 15s")],
            [KeyboardButton(text="⬅️ Quay Lại")],
        ],
        resize_keyboard=True,
    )


def topup_confirm_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Xác Nhận Đã Chuyển Khoản")],
            [KeyboardButton(text="⬅️ Quay Lại")],
        ],
        resize_keyboard=True,
    )



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

# =========================
# START
# =========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    data = load_data()
    user_id = message.from_user.id

    if not is_authorized(data, user_id):
        await message.answer(
            "🙅🏻‍♂️Bạn Chưa Được Cấp Quyền Để Truy Cập/Sử Dụng Bot.\n"
            "Vui Lòng Liên Hệ Admin !"
        )
        return

    if user_id in state_store:
        del state_store[user_id]

    await message.answer(
        build_start_text(data, user_id, message.from_user.full_name),
        reply_markup=role_menu(data, user_id),
    )


async def validate_user_id(bot, message, uid):
    try:
        await bot.get_chat(uid)
        return True
    except Exception:
        await message.answer("❌ ID này không hợp lệ hoặc người dùng chưa từng tương tác với bot.\nVui lòng yêu cầu họ ấn /start trước.")
        return False

# =========================
# MAIN HANDLER
# =========================
@dp.message()
async def handle_message(message: types.Message):
    data = load_data()
    user_id = message.from_user.id
    text = (message.text or "").strip()

    if not is_authorized(data, user_id):
        await message.answer(
            "🙅🏻‍♂️Bạn Chưa Được Cấp Quyền Để Truy Cập/Sử Dụng Bot.\n"
            "Vui Lòng Liên Hệ Admin !"
        )
        return

    user = get_user(data, user_id)
    if not user:
        await message.answer("❌ Không tìm thấy người dùng.")
        return

    # =========================
    # GLOBAL BUTTON HANDLERS (ABORT STATE)
    # =========================
    if text == "⬅️ Quay Lại":
        if user_id in state_store:
            del state_store[user_id]
        await message.answer("🔙 Đã quay lại menu chính.", reply_markup=role_menu(data, user_id))
        return

    KNOWN_BUTTONS = {
        "🚀 Up Locket Gold", "💎 Cộng Số Dư", "➖ Trừ Số Dư", "⚙️ Setup Giá", "🔐 Cấp Quyền", "💰 Xem Số Dư", "📜 Lịch Sử Đơn",
        "💎 Nạp", "💎 Cộng Số Dư CTV", "⚙️ Setup Giá CTV", "📋 Danh Sách Cộng Tác Viên", "➕ Thêm CTV", "➖ Xóa CTV",
        "📦 Locket Gold Username ( Quay Clip 3s )", "📦 Locket Gold Username ( Quay Clip 15s )",
        "🏆 Cấp Quyền Đại Lý", "🏅 Cấp Quyền CTV", "📋 Danh Sách Đại Lý", "📋 Danh Sách CTV Toàn Bộ", "➖ Xóa Đại Lý",
        "💵 Set Giá Gói 3s", "💵 Set Giá Gói 15s", "🎯 Set Giá Riêng User",
        "💵 Set Giá CTV Gói 3s", "💵 Set Giá CTV Gói 15s",
    }
    if text in KNOWN_BUTTONS and user_id in state_store:
        del state_store[user_id]

    
    # =========================
    # STATE FLOW
    # =========================
    if user_id in state_store:
        state = state_store[user_id]
        action = state["action"]

        if action == "await_add_agent_id":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            if not await validate_user_id(bot, message, uid):
                return
            state_store[user_id] = {"action": "await_add_agent_name", "target_id": uid}
            await message.answer("📝 Nhập tên cho Đại Lý:", reply_markup=cancel_only_menu())
            return

        if action == "await_add_agent_name":
            target_id = state["target_id"]
            target_name = text.strip()
            if not target_name:
                await message.answer("❌ Tên không được để trống.")
                return
            if str(target_id) in data["users"]:
                await message.answer("⚠️ ID này đã tồn tại trong hệ thống.")
            else:
                data["users"][str(target_id)] = {
                    "role": "agent",
                    "name": target_name,
                    "balance": 0,
                    "parent_id": str(ADMIN_ID),
                }
                save_data(data)
                await message.answer(
                    f"✅ Đã cấp quyền Đại Lý\n🆔 ID: {target_id}\n👤 Tên: {target_name}"
                )
            del state_store[user_id]
            return

        if action == "await_add_ctv_admin_id":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            if not await validate_user_id(bot, message, uid):
                return
            state_store[user_id] = {"action": "await_add_ctv_admin_name", "target_id": uid}
            await message.answer("📝 Nhập tên cho CTV:", reply_markup=cancel_only_menu())
            return

        if action == "await_add_ctv_admin_name":
            target_id = state["target_id"]
            target_name = text.strip()
            if not target_name:
                await message.answer("❌ Tên không được để trống.")
                return
            if str(target_id) in data["users"]:
                await message.answer("⚠️ ID này đã tồn tại trong hệ thống.")
            else:
                data["users"][str(target_id)] = {
                    "role": "collaborator",
                    "name": target_name,
                    "balance": 0,
                    "parent_id": str(ADMIN_ID),
                }
                save_data(data)
                await message.answer(
                    f"✅ Đã cấp quyền CTV\n🆔 ID: {target_id}\n👤 Tên: {target_name}"
                )
            del state_store[user_id]
            return

        if action == "await_remove_agent_id":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            target = get_user(data, uid)
            if not target or target["role"] != "agent":
                await message.answer("⚠️ Không tìm thấy Đại Lý.")
            else:
                del data["users"][str(uid)]
                data["prices"]["admin_user_custom"].pop(str(uid), None)
                data["prices"]["agent_ctv_custom"].pop(str(uid), None)
                save_data(data)
                await message.answer(f"✅ Đã xóa Đại Lý ID {uid}.", reply_markup=role_menu(data, user_id))
            del state_store[user_id]
            return

        if action == "await_remove_ctv_id":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            target = get_user(data, uid)
            if not target or target["role"] != "collaborator":
                await message.answer("⚠️ Không tìm thấy CTV.")
            else:
                parent_id = target.get("parent_id")
                if parent_id and parent_id in data["prices"]["agent_ctv_custom"]:
                    data["prices"]["agent_ctv_custom"][parent_id].pop(str(uid), None)
                data["prices"]["admin_user_custom"].pop(str(uid), None)
                del data["users"][str(uid)]
                save_data(data)
                await message.answer(f"✅ Đã xóa CTV ID {uid}.", reply_markup=role_menu(data, user_id))
            del state_store[user_id]
            return

        if action == "await_admin_add_balance_target":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            if not get_user(data, uid):
                await message.answer("⚠️ Không tìm thấy người dùng.")
                return
            state_store[user_id] = {"action": "await_admin_add_balance_amount", "target_id": uid}
            await message.answer("📝 Nhập số 💎 muốn cộng:", reply_markup=cancel_only_menu())
            return

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

        if action == "await_admin_add_balance_amount":
            amount = parse_positive_int(text)
            if amount is None:
                await message.answer("❌ Số dư phải là số.")
                return
            target_id = state["target_id"]
            add_balance(data, target_id, amount)
            save_data(data)
            await message.answer(f"✅ Đã cộng {amount}💎 cho ID {target_id}.", reply_markup=role_menu(data, user_id))
            del state_store[user_id]
            return

        if action == "await_agent_add_ctv_id":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            if not await validate_user_id(bot, message, uid):
                return
            state_store[user_id] = {"action": "await_agent_add_ctv_name", "target_id": uid}
            await message.answer("📝 Nhập tên cho CTV:", reply_markup=cancel_only_menu())
            return

        if action == "await_agent_add_ctv_name":
            target_id = state["target_id"]
            target_name = text.strip()
            if not target_name:
                await message.answer("❌ Tên không được để trống.")
                return
            if str(target_id) in data["users"]:
                await message.answer("⚠️ ID này đã tồn tại trong hệ thống.")
            else:
                data["users"][str(target_id)] = {
                    "role": "collaborator",
                    "name": target_name,
                    "balance": 0,
                    "parent_id": str(user_id),
                }
                save_data(data)
                await message.answer(
                    f"✅ Đã thêm CTV\n🆔 ID: {target_id}\n👤 Tên: {target_name}"
                )
            del state_store[user_id]
            return

        if action == "await_agent_remove_ctv_id":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            target = get_user(data, uid)
            if not target or target["role"] != "collaborator" or target["parent_id"] != str(user_id):
                await message.answer("⚠️ Không tìm thấy CTV thuộc quyền của bạn.")
            else:
                data["prices"]["agent_ctv_custom"].setdefault(str(user_id), {})
                data["prices"]["agent_ctv_custom"][str(user_id)].pop(str(uid), None)
                del data["users"][str(uid)]
                save_data(data)
                await message.answer(f"✅ Đã xóa CTV ID {uid}.", reply_markup=role_menu(data, user_id))
            del state_store[user_id]
            return

        if action == "await_agent_add_balance_ctv_id":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            target = get_user(data, uid)
            if not target or target["role"] != "collaborator" or target["parent_id"] != str(user_id):
                await message.answer("⚠️ Không tìm thấy CTV thuộc quyền của bạn.")
                return
            state_store[user_id] = {"action": "await_agent_add_balance_amount", "target_id": uid}
            await message.answer("📝 Nhập số 💎 muốn cộng cho CTV:", reply_markup=cancel_only_menu())
            return

        if action == "await_agent_add_balance_amount":
            amount = parse_positive_int(text)
            if amount is None:
                await message.answer("❌ Số dư phải là số.")
                return
            if amount < 10 or amount % 2 != 0:
                await message.answer("❌ Đại Lý chỉ được cộng từ 10💎 trở lên và phải là số chẵn.")
                return
            if user["balance"] < amount:
                await message.answer("❌ Vui lòng nạp thêm 💎")
                del state_store[user_id]
                return
            target_id = state["target_id"]
            target = get_user(data, target_id)
            if not target or target["role"] != "collaborator" or target["parent_id"] != str(user_id):
                await message.answer("⚠️ Không tìm thấy CTV thuộc quyền của bạn.")
                del state_store[user_id]
                return
            user["balance"] -= amount
            add_balance(data, target_id, amount)
            save_data(data)
            await message.answer(f"✅ Đã cộng {amount}💎 cho CTV ID {target_id}.", reply_markup=role_menu(data, user_id))
            del state_store[user_id]
            return

        if action == "await_topup_amount":
            amount = parse_positive_int(text)
            if amount is None:
                await message.answer("❌ Vui lòng nhập số hợp lệ.")
                return
            if amount < 100:
                await message.answer("❌ Vui lòng nạp tối thiểu 100💎")
                return
            state_store[user_id] = {"action": "await_topup_confirm", "amount": amount}
            try:
                photo = FSInputFile(QR_IMAGE)
                await message.answer_photo(
                    photo=photo,
                    caption=(
                        f"💎 Nạp số dư: {amount}💎\n"
                        "👉 Quét mã QR để chuyển khoản\n"
                        f"👉 Nội dung chuyển khoản: {amount}\n"
                        "👉 Sau khi chuyển khoản, bấm nút xác nhận bên dưới"
                    ),
                    reply_markup=topup_confirm_menu(),
                )
            except Exception:
                await message.answer(
                    "❌ Không tìm thấy ảnh QR. Kiểm tra file qr.png",
                    reply_markup=topup_confirm_menu(),
                )
            return

        if action == "await_topup_confirm":
            if text != "✅ Xác Nhận Đã Chuyển Khoản":
                await message.answer("👉 Bấm nút xác nhận hoặc quay lại.")
                return
            amount = state["amount"]
            requester = get_user(data, user_id)
            data["pending_topups"].append(
                {
                    "user_id": user_id,
                    "user_name": requester["name"],
                    "role": requester["role"],
                    "amount": amount,
                    "created_at": now_str(),
                    "status": "pending",
                }
            )
            save_data(data)
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
                    "🔔 Có yêu cầu nạp tiền mới\n"
                    f"🆔 ID: {user_id}\n"
                    f"👤 Tên: {requester['name']}\n"
                    f"🏷 Vai trò: {requester['role']}\n"
                    f"💎 Số lượng: {amount}\n"
                    f"🕒 {now_str()}",
                    reply_markup=topup_markup
                )
            except Exception:
                pass
            if requester["role"] == "collaborator" and requester.get("parent_id") and requester["parent_id"] != str(ADMIN_ID):
                try:
                    await bot.send_message(
                        int(requester["parent_id"]),
                        "🔔 CTV của bạn vừa gửi yêu cầu nạp tiền\n"
                        f"🆔 ID: {user_id}\n"
                        f"👤 Tên: {requester['name']}\n"
                        f"💎 Số lượng: {amount}\n"
                        f"🕒 {now_str()}",
                    )
                except Exception:
                    pass
            await message.answer(
                "✅ Đã gửi yêu cầu xác nhận chuyển khoản.\nVui lòng chờ Admin/Đại Lý xác nhận.",
                reply_markup=role_menu(data, user_id),
            )
            del state_store[user_id]
            return

        if action == "await_set_global_price_3s":
            amount = parse_positive_int(text)
            if amount is None:
                await message.answer("❌ Giá phải là số hợp lệ.")
                return
            data["prices"]["global"]["package_3s"] = amount
            save_data(data)
            await message.answer(f"✅ Đã setup giá gói 3s = {amount}💎", reply_markup=role_menu(data, user_id))
            del state_store[user_id]
            return

        if action == "await_set_global_price_15s":
            amount = parse_positive_int(text)
            if amount is None:
                await message.answer("❌ Giá phải là số hợp lệ.")
                return
            data["prices"]["global"]["package_15s"] = amount
            save_data(data)
            await message.answer(f"✅ Đã setup giá gói 15s = {amount}💎", reply_markup=role_menu(data, user_id))
            del state_store[user_id]
            return

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

        if action == "await_admin_custom_price_target":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            if not get_user(data, uid):
                await message.answer("⚠️ Không tìm thấy người dùng.")
                return
            state_store[user_id] = {"action": "await_admin_custom_price_package", "target_id": uid}
            await message.answer("👉 Chọn gói 3s hoặc 15s:", reply_markup=package_type_menu())
            return

        if action == "await_admin_custom_price_package":
            if text not in ["Gói 3s", "Gói 15s"]:
                await message.answer("❌ Chọn Gói 3s hoặc Gói 15s.")
                return
            package_key = "package_3s" if text == "Gói 3s" else "package_15s"
            state_store[user_id] = {
                "action": "await_admin_custom_price_amount",
                "target_id": state["target_id"],
                "package_key": package_key,
            }
            await message.answer("📝 Nhập giá muốn setup:", reply_markup=cancel_only_menu())
            return

        if action == "await_admin_custom_price_amount":
            amount = parse_positive_int(text)
            if amount is None:
                await message.answer("❌ Giá phải là số hợp lệ.")
                return
            target_id = state["target_id"]
            package_key = state["package_key"]
            data["prices"]["admin_user_custom"].setdefault(str(target_id), {})
            data["prices"]["admin_user_custom"][str(target_id)][package_key] = amount
            save_data(data)
            await message.answer(
                f"✅ Đã set giá riêng cho ID {target_id}\n{package_label(package_key)} = {amount}💎"
            )
            del state_store[user_id]
            return

        if action == "await_agent_set_ctv_price_target":
            uid = parse_user_id(text)
            if uid is None:
                await message.answer("❌ ID Telegram phải là số.")
                return
            target = get_user(data, uid)
            if not target or target["role"] != "collaborator" or target["parent_id"] != str(user_id):
                await message.answer("⚠️ Không tìm thấy CTV thuộc quyền của bạn.")
                return
            state_store[user_id] = {
                "action": "await_agent_set_ctv_price_amount",
                "target_id": uid,
                "package_key": state["package_key"],
            }
            await message.answer("📝 Nhập giá muốn setup cho CTV:", reply_markup=cancel_only_menu())
            return

        if action == "await_agent_set_ctv_price_amount":
            amount = parse_positive_int(text)
            if amount is None:
                await message.answer("❌ Giá phải là số hợp lệ.")
                return
            if amount < 40:
                await message.answer("❌ Đại Lý chỉ được setup giá từ 40💎 trở lên.")
                return
            target_id = state["target_id"]
            package_key = state["package_key"]
            data["prices"]["agent_ctv_custom"].setdefault(str(user_id), {})
            data["prices"]["agent_ctv_custom"][str(user_id)].setdefault(str(target_id), {})
            data["prices"]["agent_ctv_custom"][str(user_id)][str(target_id)][package_key] = amount
            save_data(data)
            await message.answer(
                f"✅ Đã set giá cho CTV ID {target_id}\n{package_label(package_key)} = {amount}💎"
            )
            del state_store[user_id]
            return

        if action == "await_package_username":
            package_key = state["package_key"]
            username = text.strip()
            await message.answer("⏳Đang Check ID/Username")
            checked = await check_account_mock(username)
            if not checked["ok"]:
                await message.answer(
                    "❌Xử Lý Thất Bại\n"
                    "🙅🏻‍♂️ID/Username Không Tồn Tại Hoặc Để Chế Độ Riêng Tư\n"
                    "🔎 Kiểm Tra Lại ID/Username",
                    reply_markup=role_menu(data, user_id),
                )
                del state_store[user_id]
                return
            price = get_effective_price(data, user_id, package_key)
            if price is None:
                await message.answer("❌ Không xác định được giá đơn hàng.")
                del state_store[user_id]
                return
            ok, reason = deduct_balance(data, user_id, price)
            if not ok:
                await message.answer(f"❌ {reason}", reply_markup=role_menu(data, user_id))
                del state_store[user_id]
                return
            result = await create_order_mock(username, package_key)
            if not result["ok"]:
                await message.answer(
                    "❌Xử Lý Thất Bại\n"
                    "🙅🏻‍♂️ID/Username Không Tồn Tại Hoặc Để Chế Độ Riêng Tư\n"
                    "🔎 Kiểm Tra Lại ID/Username",
                    reply_markup=role_menu(data, user_id),
                )
                del state_store[user_id]
                return
            data["orders"].append(
                {
                    "operator_id": user_id,
                    "operator_name": user["name"],
                    "operator_role": user["role"],
                    "package_key": package_key,
                    "customer_name": result["display_name"],
                    "start_time": result["start_time"],
                    "end_time": result["end_time"],
                    "price": price,
                    "created_at": now_str(),
                }
            )
            save_data(data)
            cost_line = ""
            if user["role"] != "admin":
                cost_line = f"\n💎 Đã Trừ: {price}"
            await message.answer(
                "✅Xử Lý Thành Công\n"
                f"👤Khách : {result['display_name']}\n"
                f"{package_label(package_key)}\n"
                f"🕒 Bắt Đầu: {result['start_time']}\n"
                f"⏰ Hết Hạn: {result['end_time']}"
                f"{cost_line}",
                reply_markup=role_menu(data, user_id),
            )
            del state_store[user_id]
            return

    # =========================
    # COMMON BUTTONS
    # =========================
    if text == "💰 Xem Số Dư":
        await message.answer(f"💎 Số Dư Hiện Tại: {user['balance']}")
        return

    if text == "📜 Lịch Sử Đơn":
        rows = get_last_orders_for_user(data, user_id)
        if not rows:
            await message.answer("📭 Chưa có lịch sử đơn.")
            return
        lines = []
        for item in rows:
            lines.append(
                f"{package_label(item['package_key'])}\n"
                f"👤 {item['customer_name']}\n"
                f"💎 {item['price']}\n"
                f"🕒 {item['created_at']}"
            )
        if is_admin(user_id):
            history_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🗑 Xóa toàn bộ lịch sử", callback_data="delete_history_all")],
                    [InlineKeyboardButton(text="🗑 Xóa lịch sử theo ID", callback_data="delete_history_user")]
                ]
            )
            await message.answer("\n\n".join(lines), reply_markup=history_markup)
        else:
            await message.answer("\n\n".join(lines))
        return

    if text == "🚀 Up Locket Gold":
        await message.answer("👉 Chọn gói:", reply_markup=package_menu())
        return

    pkg = package_key_from_text(text)
    if pkg:
        state_store[user_id] = {"action": "await_package_username", "package_key": pkg}
        await message.answer("📝Nhập ID/Username")
        return

    if text == "💎 Nạp":
        state_store[user_id] = {"action": "await_topup_amount"}
        await message.answer("📝 Nhập số 💎 muốn nạp (tối thiểu 100💎):")
        return

    # =========================
    # ADMIN BUTTONS
    # =========================
    if is_admin(user_id):
        if text == "🔐 Cấp Quyền":
            await message.answer("🔐 Chọn chức năng:", reply_markup=permission_menu())
            return
        if text == "🏆 Cấp Quyền Đại Lý":
            state_store[user_id] = {"action": "await_add_agent_id"}
            await message.answer("📝 Nhập ID Telegram Đại Lý:", reply_markup=cancel_only_menu())
            return
        if text == "🏅 Cấp Quyền CTV":
            state_store[user_id] = {"action": "await_add_ctv_admin_id"}
            await message.answer("📝 Nhập ID Telegram CTV:", reply_markup=cancel_only_menu())
            return
        if text == "➖ Xóa Đại Lý":
            state_store[user_id] = {"action": "await_remove_agent_id"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram Đại Lý cần xóa:", reply_markup=select_agent_menu(data))
            return
        if text == "➖ Xóa CTV":
            state_store[user_id] = {"action": "await_remove_ctv_id"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần xóa:", reply_markup=select_ctv_menu(data))
            return
        if text == "📋 Danh Sách Đại Lý":
            lines = [
                f"🆔 {uid} - 👤 {info['name']} - 💎 {info['balance']}"
                for uid, info in data["users"].items()
                if info["role"] == "agent"
            ]
            await message.answer("\n".join(lines) if lines else "📭 Chưa có Đại Lý.")
            return
        if text == "📋 Danh Sách CTV Toàn Bộ":
            lines = [
                f"🆔 {uid} - 👤 {info['name']} - 💎 {info['balance']} - Parent: {info['parent_id']}"
                for uid, info in data["users"].items()
                if info["role"] == "collaborator"
            ]
            await message.answer("\n".join(lines) if lines else "📭 Chưa có CTV.")
            return
        if text == "💎 Cộng Số Dư":
            state_store[user_id] = {"action": "await_admin_add_balance_target"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram cần cộng số dư:", reply_markup=select_all_users_menu(data))
            return
        if text == "➖ Trừ Số Dư":
            state_store[user_id] = {"action": "await_admin_sub_balance_target"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram cần trừ số dư:", reply_markup=select_all_users_menu(data))
            return
        if text == "⚙️ Setup Giá":
            await message.answer("⚙️ Chọn chức năng setup giá:", reply_markup=admin_price_menu())
            return
        if text == "💵 Set Giá Gói 3s":
            state_store[user_id] = {"action": "await_set_global_price_3s"}
            await message.answer("📝 Nhập giá mới cho gói 3s:", reply_markup=cancel_only_menu())
            return
        if text == "💵 Set Giá Gói 15s":
            state_store[user_id] = {"action": "await_set_global_price_15s"}
            await message.answer("📝 Nhập giá mới cho gói 15s:", reply_markup=cancel_only_menu())
            return
        if text == "🎯 Set Giá Riêng User":
            state_store[user_id] = {"action": "await_admin_custom_price_target"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram cần setup giá riêng:", reply_markup=select_all_users_menu(data))
            return

    # =========================
    # AGENT BUTTONS
    # =========================
    if is_agent(data, user_id):
        if text == "📋 Danh Sách Cộng Tác Viên":
            lines = []
            for uid, info in data["users"].items():
                if info["role"] == "collaborator" and info["parent_id"] == str(user_id):
                    ctv_prices = data["prices"]["agent_ctv_custom"].get(str(user_id), {}).get(uid, {})
                    p3 = ctv_prices.get("package_3s", "-")
                    p15 = ctv_prices.get("package_15s", "-")
                    lines.append(f"🆔 {uid} - 👤 {info['name']} - 💎 {info['balance']} - 3s:{p3} - 15s:{p15}")
            await message.answer("\n".join(lines) if lines else "📭 Chưa có Cộng Tác Viên nào thuộc quyền của bạn.")
            return
        if text == "➕ Thêm CTV":
            state_store[user_id] = {"action": "await_agent_add_ctv_id"}
            await message.answer("📝 Nhập ID Telegram CTV:", reply_markup=cancel_only_menu())
            return
        if text == "➖ Xóa CTV":
            state_store[user_id] = {"action": "await_agent_remove_ctv_id"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần xóa:", reply_markup=select_ctv_menu(data))
            return
        if text == "💎 Cộng Số Dư CTV":
            state_store[user_id] = {"action": "await_agent_add_balance_ctv_id"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần cộng số dư:", reply_markup=select_ctv_menu(data, user_id))
            return
        if text == "⚙️ Setup Giá CTV":
            await message.answer("⚙️ Chọn chức năng setup giá:", reply_markup=agent_price_menu())
            return
        if text == "💵 Set Giá CTV Gói 3s":
            state_store[user_id] = {"action": "await_agent_set_ctv_price_target", "package_key": "package_3s"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần setup giá gói 3s:", reply_markup=select_ctv_menu(data, user_id))
            return
        if text == "💵 Set Giá CTV Gói 15s":
            state_store[user_id] = {"action": "await_agent_set_ctv_price_target", "package_key": "package_15s"}
            await message.answer("📝 Chọn hoặc nhập ID Telegram CTV cần setup giá gói 15s:", reply_markup=select_ctv_menu(data, user_id))
            return

    await message.answer("Bạn bấm nút trong menu để dùng bot.", reply_markup=role_menu(data, user_id))



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
    
    new_text = callback_query.message.text + "\n\n✅ Đã Duyệt!"
    await callback_query.message.edit_text(new_text)
    await callback_query.answer("✅ Đã cộng tiền thành công!")



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


async def main():
    print("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
