import io
import os
from PIL import Image, ImageDraw, ImageFont

def generate_trainer_card(user_data, team=None):
    # Dimensions
    WIDTH, HEIGHT = 480, 320
    
    # Colors
    BG_BEIGE = "#f8ebd0"
    BORDER_RED = "#d95c50"
    TEXT_BLACK = "#1a1a1a"
    
    # Create base image
    img = Image.new("RGB", (WIDTH, HEIGHT), BORDER_RED)
    draw = ImageDraw.Draw(img)
    
    # Draw inner beige frame
    draw.rectangle([8, 8, WIDTH-8, HEIGHT-8], fill=BG_BEIGE, outline="#000000", width=2)
    
    # Top red header
    draw.rectangle([12, 12, WIDTH-12, 50], fill=BORDER_RED)
    
    # Load fonts
    font_path = os.path.join(os.path.dirname(__file__), "assets", "font.ttf")
    
    try:
        title_font = ImageFont.truetype(font_path, 20)  # Smaller title
        text_font = ImageFont.truetype(font_path, 14)   # Smaller text
        small_font = ImageFont.truetype(font_path, 10)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Draw Title (Center Top, Black)
    title_text = "TRAINER CARD"
    # Estimate width to center (since getsize is deprecated, use basic math)
    # A standard pixel font is roughly 12px per char at size 20
    title_x = (WIDTH - (len(title_text) * 12)) // 2
    draw.text((title_x, 20), title_text, font=title_font, fill=TEXT_BLACK)
    
    # Draw ID (Bottom corner)
    user_id = str(user_data.get('_id', '000000'))
    # Use a wider margin from the right edge to prevent overflow
    draw.text((WIDTH - 200, HEIGHT - 30), f"IDNo.{user_id}", font=small_font, fill=TEXT_BLACK)
    
    # Draw Name (Truncate to 12 chars to prevent overflow)
    name_str = user_data.get('first_name') or user_data.get('username', 'Unknown')
    username = str(name_str)[:12].upper()
    draw.text((20, 65), f"NAME: {username}", font=title_font, fill=TEXT_BLACK)
    
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
    
    draw.text((stat_x, y_start), f"ELO: {elo}", font=text_font, fill=TEXT_BLACK)
    draw.text((stat_x, y_start + spacing), f"AVG DMG: {avg_dmg}", font=text_font, fill=TEXT_BLACK)
    draw.text((stat_x, y_start + spacing * 2), f"DEX: {dex_seen} / 493", font=text_font, fill=TEXT_BLACK)
    draw.text((stat_x, y_start + spacing * 3), f"W/L: {wins}W - {losses}L", font=text_font, fill=TEXT_BLACK)
    draw.text((stat_x, y_start + spacing * 4), f"WIN RATE: {win_rate}%", font=text_font, fill=TEXT_BLACK)

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
    else:
        # Draw a big Pokeball in the empty space on the left
        pb_x = 55
        pb_y = 125
        pb_size = 130
        
        # Base white circle with black outline
        draw.ellipse([pb_x, pb_y, pb_x + pb_size, pb_y + pb_size], fill="#ffffff", outline="#1a1a1a", width=4)
        
        # Top red half (chord)
        draw.chord([pb_x, pb_y, pb_x + pb_size, pb_y + pb_size], start=180, end=360, fill="#d95c50", outline="#1a1a1a", width=2)
        
        # Middle black band
        band_y = pb_y + (pb_size // 2) - 4
        draw.rectangle([pb_x + 2, band_y, pb_x + pb_size - 2, band_y + 8], fill="#1a1a1a")
        
        # Center button (outer black circle)
        btn_size = 36
        btn_x = pb_x + (pb_size // 2) - (btn_size // 2)
        btn_y = pb_y + (pb_size // 2) - (btn_size // 2)
        draw.ellipse([btn_x, btn_y, btn_x + btn_size, btn_y + btn_size], fill="#1a1a1a")
        
        # Center button (inner white circle)
        ibtn_size = 20
        ibtn_x = pb_x + (pb_size // 2) - (ibtn_size // 2)
        ibtn_y = pb_y + (pb_size // 2) - (ibtn_size // 2)
        draw.ellipse([ibtn_x, ibtn_y, ibtn_x + ibtn_size, ibtn_y + ibtn_size], fill="#ffffff", outline="#a0a0a0", width=1)
    # Save to bytes
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
