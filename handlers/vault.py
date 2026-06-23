from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import config
from database import db

ALL_COLLECTIBLES = [
    "poke_ball",
    "great_ball",
    "ultra_ball",
    "master_ball",
    "gs_ball",
    "squirtle_squad",
    "mew",
    "red_sprite"
]

def build_vault_text(first_name, collectibles, active):
    lines = [f"<b>Vault - {first_name}</b>\n"]
    
    for i, item in enumerate(ALL_COLLECTIBLES):
        prefix = "┍" if i == 0 else ("┕" if i == len(ALL_COLLECTIBLES)-1 else "┝")
        if item == active:
            symbol = "◆"
        else:
            symbol = "◈" if item in collectibles else "◇"
            
        name = item.replace('_', ' ').title()
        
        lines.append(f"{prefix}{symbol} {name}")
        if i < len(ALL_COLLECTIBLES)-1:
            lines.append("│")
            
    lines.append("\n◆ [equipped]")
    lines.append("◈ [owned]")
    lines.append("◇ [not owned]")
    return "\n".join(lines)

def build_vault_buttons(collectibles, active, page=0):
    ITEMS_PER_PAGE = 4
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    
    current_items = collectibles[start_idx:end_idx]
    
    buttons = []
    row = []
    for item in current_items:
        display_name = item.replace('_', ' ').title()
        if item == active:
            display_name = f"✅ {display_name}"
        
        row.append(InlineKeyboardButton(display_name, callback_data=f"equip_{item}:{page}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
            
    if row:
        buttons.append(row)
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"equip_page:{page-1}"))
    if end_idx < len(collectibles):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"equip_page:{page+1}"))
        
    if nav_row:
        buttons.append(nav_row)
        
    if active:
        buttons.append([InlineKeyboardButton("❌ Unequip Current", callback_data=f"equip_none:{page}")])
        
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
    
    text = build_vault_text(username, collectibles, active)
    reply_markup = build_vault_buttons(collectibles, active, page=0)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

async def handle_equip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_', 1)
    if len(data) < 2: return
    
    item_and_page = data[1]
    
    if ':' in item_and_page:
        item, page_str = item_and_page.split(':')
        page = int(page_str)
    else:
        item = item_and_page
        page = 0
        
    user_id = query.from_user.id
    
    if item == "page":
        await query.answer()
    elif item == "none":
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
    
    text = build_vault_text(username, collectibles, active)
    reply_markup = build_vault_buttons(collectibles, active, page)
    
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        pass
