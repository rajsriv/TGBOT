from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db

async def handle_vault_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_db = await db.get_user(user.id)
    if not user_db:
        await update.message.reply_text("You haven't registered yet! Use /start first.")
        return
        
    collectibles = user_db.get("collectibles", [])
    active = user_db.get("active_collectible")
    
    if not collectibles:
        await update.message.reply_text("You don't own any collectibles yet! Keep battling to unlock them.")
        return
        
    text = "🎒 <b>Your Vault</b>\n\nSelect a collectible to display on your trainer card:"
    
    buttons = []
    for item in collectibles:
        display_name = item.replace('_', ' ').title()
        if item == active:
            display_name = f"✅ {display_name}"
            
        buttons.append([InlineKeyboardButton(display_name, callback_data=f"equip_{item}")])
        
    if active:
        buttons.append([InlineKeyboardButton("❌ Unequip Current", callback_data="equip_none")])
        
    reply_markup = InlineKeyboardMarkup(buttons)
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
        if item in user_db.get("collectibles", []):
            await db.set_active_collectible(user_id, item)
            await query.answer(f"Equipped {item.replace('_', ' ').title()}!")
        else:
            await query.answer("You don't own this collectible!", show_alert=True)
            return
            
    # Refresh vault view
    user_db = await db.get_user(user_id)
    collectibles = user_db.get("collectibles", [])
    active = user_db.get("active_collectible")
    
    text = "🎒 <b>Your Vault</b>\n\nSelect a collectible to display on your trainer card:"
    buttons = []
    for c_item in collectibles:
        display_name = c_item.replace('_', ' ').title()
        if c_item == active:
            display_name = f"✅ {display_name}"
        buttons.append([InlineKeyboardButton(display_name, callback_data=f"equip_{c_item}")])
        
    if active:
        buttons.append([InlineKeyboardButton("❌ Unequip Current", callback_data="equip_none")])
        
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_reply_markup(reply_markup=reply_markup)
