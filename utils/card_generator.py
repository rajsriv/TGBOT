import io
import os
from PIL import Image, ImageDraw, ImageFont

def generate_trainer_card(user_data, team=None):
    # Dimensions
    WIDTH, HEIGHT = 480, 320
    
    # Create base image
    img = Image.new("RGB", (WIDTH, HEIGHT), "#3bb59b")
    draw = ImageDraw.Draw(img)
    
    # Draw main card frame
    # Outer white border
    draw.rectangle([10, 10, WIDTH-10, HEIGHT-10], fill="#ffffff", outline="#313131", width=2)
    
    # Top blue header
    draw.rectangle([12, 12, WIDTH-12, 60], fill="#6b9ced")
    
    # Bottom blue header (for badges area)
    draw.rectangle([12, HEIGHT-60, WIDTH-12, HEIGHT-12], fill="#84b5e8")
    
    # Load fonts
    font_path = os.path.join(os.path.dirname(__file__), "assets", "font.ttf")
    
    try:
        title_font = ImageFont.truetype(font_path, 24)
        text_font = ImageFont.truetype(font_path, 16)
        small_font = ImageFont.truetype(font_path, 12)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Draw Title
    draw.text((20, 25), "TRAINER CARD", font=title_font, fill="#f8d868", stroke_width=1, stroke_fill="#4a4a4a")
    
    # Draw ID (Full ID in bottom bar)
    user_id = str(user_data.get('_id', '000000'))
    draw.text((WIDTH - 250, HEIGHT - 40), f"IDNo.{user_id}", font=text_font, fill="#4a4a4a")
    
    # Draw Name (Truncate to 12 chars to prevent overflow)
    name_str = user_data.get('first_name') or user_data.get('username', 'Unknown')
    username = str(name_str)[:12].upper()
    draw.text((20, 80), f"NAME: {username}", font=title_font, fill="#4a4a4a")
    
    # Draw Stats on the right side
    stat_x = 260
    y_start = 100
    spacing = 30
    
    wins = user_data.get('wins', 0)
    losses = user_data.get('losses', 0)
    total_dmg = user_data.get('total_damage', 0)
    total_battles = wins + losses
    avg_dmg = int(total_dmg / total_battles) if total_battles > 0 else 0
    win_rate = int((wins / total_battles) * 100) if total_battles > 0 else 0
    dex_seen = len(user_data.get('dex', []))
    elo = user_data.get('elo', 1000)
    
    draw.text((stat_x, y_start), f"ELO: {elo}", font=text_font, fill="#4a4a4a")
    draw.text((stat_x, y_start + spacing), f"AVG DMG: {avg_dmg}", font=text_font, fill="#4a4a4a")
    draw.text((stat_x, y_start + spacing * 2), f"DEX: {dex_seen} / 493", font=text_font, fill="#4a4a4a")
    draw.text((stat_x, y_start + spacing * 3), f"W/L: {wins}W - {losses}L", font=text_font, fill="#4a4a4a")
    draw.text((stat_x, y_start + spacing * 4), f"WIN RATE: {win_rate}%", font=text_font, fill="#4a4a4a")

    if team:
        start_x = 20
        start_y = 125
        box_w, box_h = 70, 70
        gap = 5
        
        for i, pkmn in enumerate(team):
            if i >= 6: break
            row = i // 3
            col = i % 3
            x = start_x + col * (box_w + gap)
            y = start_y + row * (box_h + gap)
            
            draw.rectangle([x, y, x + box_w, y + box_h], outline="#313131", fill="#ffffff", width=2)
            
            if "sprite" in pkmn and pkmn["sprite"]:
                try:
                    sprite_img = Image.open(io.BytesIO(pkmn["sprite"])).convert("RGBA")
                    sprite_img = sprite_img.resize((64, 64), Image.NEAREST)
                    
                    if pkmn.get("hp", 1) <= 0:
                        # Grayscale for fainted
                        la = sprite_img.convert("LA")
                        sprite_img = la.convert("RGBA")
                        
                    img.paste(sprite_img, (x + 3, y + 3), sprite_img)
                except Exception as e:
                    pass
    
    # Save to bytes
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
