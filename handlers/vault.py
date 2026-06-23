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

def build_vault_text(first_name, collectibles, active, is_group=False):
    lines = [f"<b>Vault - {first_name}</b>\n"]
    
    display_items = [item for item in ALL_COLLECTIBLES if item in collectibles] if is_group else ALL_COLLECTIBLES
    
    if not display_items and is_group:
        return f"<b>Vault - {first_name}</b>\n\nEmpty!"
        
    for i, item in enumerate(display_items):
        prefix = "┍" if i == 0 else ("┕" if i == len(display_items)-1 else "┝")
        if item == active:
            symbol = "◆"
        else:
            symbol = "◈" if item in collectibles else "◇"
            
        name = item.replace('_', ' ').title()
        
        lines.append(f"{prefix}{symbol} {name}")
        if not is_group and i < len(display_items)-1:
            lines.append("│")
            
    lines.append("\n◆ [equipped]")
    if not is_group:
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
    
    text = build_vault_text(username, collectibles, active, update.effective_chat.type != "private")
    
    if update.effective_chat.type == "private":
        reply_markup = build_vault_buttons(collectibles, active, page=0)
    else:
        reply_markup = None
        
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

async def handle_reward_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if str(user.id) != config.OWNER_ID:
        await update.message.reply_text("This command is restricted to the bot owner.")
        return
        
    if len(context.args) < 2:
        items_list = "\n".join([f"{i}. {item}" for i, item in enumerate(ALL_COLLECTIBLES)])
        await update.message.reply_text(f"Usage: /reward <user_id> <item_no>\n\nItems:\n{items_list}")
        return
        
    try:
        target_id = int(context.args[0])
        item_no = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid user ID or item number.")
        return
        
    if item_no < 0 or item_no >= len(ALL_COLLECTIBLES):
        await update.message.reply_text("Invalid item number.")
        return
        
    item_name = ALL_COLLECTIBLES[item_no]
    
    target_user = await db.get_user(target_id)
    if not target_user:
        await update.message.reply_text("User not found in database.")
        return
        
    await db.unlock_collectible(target_id, item_name)
    await update.message.reply_text(f"Successfully awarded {item_name.replace('_', ' ').title()} to user {target_id}!")
    
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎉 <b>Congratulations!</b>\n\nYou've been awarded a new collectible: <b>{item_name.replace('_', ' ').title()}</b>!\nCheck it out using /vault",
            parse_mode="HTML"
        )
    except Exception:
        pass
