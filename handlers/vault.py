from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import config
from database import db

ALL_COLLECTIBLES = [
    "poke_ball",
    "great_ball",
    "squirtle_squad",
    "mew",
    "red_sprite"
]

def build_vault_text(first_name, collectibles):
    lines = [f"<b>Vault - {first_name}</b>\n"]
    
    for i, item in enumerate(ALL_COLLECTIBLES):
        prefix = "┍" if i == 0 else ("┕" if i == len(ALL_COLLECTIBLES)-1 else "┝")
        symbol = "◈" if item in collectibles else "◇"
        name = item.replace('_', ' ').title()
        
        lines.append(f"{prefix}{symbol} {name}")
        if i < len(ALL_COLLECTIBLES)-1:
            lines.append("│")
            
    lines.append("\n◈ [owned]")
    lines.append("◇ [not owned]")
    return "\n".join(lines)

def build_vault_buttons(collectibles, active):
    buttons = []
    for item in collectibles:
        display_name = item.replace('_', ' ').title()
        if item == active:
            display_name = f"✅ {display_name}"
        buttons.append([InlineKeyboardButton(display_name, callback_data=f"equip_{item}")])
        
    if active:
        buttons.append([InlineKeyboardButton("❌ Unequip Current", callback_data="equip_none")])
        
    return InlineKeyboardMarkup(buttons)

async def handle_vault_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_db = await db.get_user(user.id)
    if not user_db:
        await update.message.reply_text("You haven't registered yet! Use /start first.")
        return
        
    collectibles = user_db.get("collectibles", [])
    if str(user.id) == config.OWNER_ID:
        collectibles = ALL_COLLECTIBLES
    active = user_db.get("active_collectible")
    username = user_db.get("username", user.first_name)
    
    text = build_vault_text(username, collectibles)
    reply_markup = build_vault_buttons(collectibles, active)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

async def handle_equip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_', 1)
    if len(data) < 2: return
    
    item = data[1]
    user_id = query.from_user.id
    
    if item == "none":
        await db.set_active_collectible(user_id, None)
        await query.answer("Collectible unequipped!")
    else:
        user_db = await db.get_user(user_id)
        if item in user_db.get("collectibles", []) or str(user_id) == config.OWNER_ID:
            await db.set_active_collectible(user_id, item)
            await query.answer(f"Equipped {item.replace('_', ' ').title()}!")
        else:
            await query.answer("You don't own this collectible!", show_alert=True)
            return
            
    # Refresh vault view
    user_db = await db.get_user(user_id)
    collectibles = user_db.get("collectibles", [])
    if str(user_id) == config.OWNER_ID:
        collectibles = ALL_COLLECTIBLES
    active = user_db.get("active_collectible")
    username = user_db.get("username", query.from_user.first_name)
    
    text = build_vault_text(username, collectibles)
    reply_markup = build_vault_buttons(collectibles, active)
    
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        pass
