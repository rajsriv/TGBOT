import io
import os
from PIL import Image, ImageDraw, ImageFont

def generate_trainer_card(user_data):
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
    
    # Draw ID
    draw.text((300, 30), f"IDNo.{user_data.get('_id', '00000')}"[:15], font=text_font, fill="#4a4a4a")
    
    # Draw Name
    username = str(user_data.get('username', 'Unknown'))[:15].upper()
    draw.text((20, 80), f"NAME: {username}", font=title_font, fill="#4a4a4a")
    
    # Draw Stats
    y_start = 140
    spacing = 35
    
    # Stat Names
    draw.text((40, y_start), "ELO", font=text_font, fill="#4a4a4a")
    draw.text((40, y_start + spacing), "WIN/LOSS", font=text_font, fill="#4a4a4a")
    draw.text((40, y_start + spacing * 2), "DMG DEALT", font=text_font, fill="#4a4a4a")
    
    # Stat Values
    draw.text((220, y_start), str(user_data.get('elo', 1000)), font=text_font, fill="#4a4a4a")
    draw.text((220, y_start + spacing), f"{user_data.get('wins', 0)} / {user_data.get('losses', 0)}", font=text_font, fill="#4a4a4a")
    draw.text((220, y_start + spacing * 2), str(user_data.get('total_damage', 0)), font=text_font, fill="#4a4a4a")
    
    # Save to bytes
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
