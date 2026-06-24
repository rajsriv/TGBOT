import io
import os
from PIL import Image, ImageDraw, ImageFont

def generate_profile_card_new(user_data, team=None):
    WIDTH, HEIGHT = 736, 464
    
    bg_path = os.path.join(os.path.dirname(__file__), "assets", "trainer_card_bg.png")
    try:
        img = Image.open(bg_path).convert("RGBA")
    except Exception:
        img = Image.new("RGBA", (WIDTH, HEIGHT), "#f8ebd0")
        
    draw = ImageDraw.Draw(img)
    TEXT_BLACK = "#1a1a1a"
    TEXT_WHITE = "#ffffff"
    
    font_path = os.path.join(os.path.dirname(__file__), "assets", "font.ttf")
    try:
        name_font = ImageFont.truetype(font_path, 28)
        text_font = ImageFont.truetype(font_path, 20)
        title_font = ImageFont.truetype(font_path, 22)
    except:
        name_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        
    name_str = user_data.get('first_name') or user_data.get('username', 'Unknown')
    username = str(name_str)[:12].upper()
    try:
        name_width = draw.textlength(username, font=name_font)
    except AttributeError:
        name_width = len(username) * 16
        
    draw.text((549 - name_width/2, 20), username, font=name_font, fill=TEXT_WHITE)
    
    wins = user_data.get('wins', 0)
    losses = user_data.get('losses', 0)
    total_dmg = user_data.get('total_damage', 0)
    total_battles = wins + losses
    avg_dmg = int(total_dmg / total_battles) if total_battles > 0 else 0
    win_rate = int((wins / total_battles) * 100) if total_battles > 0 else 0
    dex_seen = len(user_data.get('dex', []))
    elo = user_data.get('elo', 1000)
    
    stat_x = 60
    y_start_top = 130
    spacing = 35
    
    draw.text((stat_x, y_start_top), f"ELO: {elo}", font=title_font, fill=TEXT_BLACK)
    draw.text((stat_x, y_start_top + spacing), f"AVG DMG: {avg_dmg}", font=text_font, fill=TEXT_BLACK)
    draw.text((stat_x, y_start_top + spacing * 2), f"DEX: {dex_seen} / 493", font=text_font, fill=TEXT_BLACK)
    
    y_start_bottom = 251
    kd_ratio = f"{(wins / losses):.2f}" if losses > 0 else f"{wins:.2f}"
    
    draw.text((stat_x, y_start_bottom), f"K/D: {kd_ratio}", font=title_font, fill=TEXT_BLACK)
    draw.text((stat_x, y_start_bottom + spacing), f"WIN %: {win_rate}%", font=text_font, fill=TEXT_BLACK)
    draw.text((stat_x, y_start_bottom + spacing * 2), f"BATTLES: {total_battles}", font=text_font, fill=TEXT_BLACK)
    
    if team:
        start_x = 60
        start_y = 280
        box_w, box_h = 60, 60
        gap = 15
        
        for i, pkmn in enumerate(team):
            if i >= 6: break
            row = i // 3
            col = i % 3
            x = start_x + col * (box_w + gap)
            y = start_y + row * (box_h + gap)
            
            if "sprite" in pkmn and pkmn["sprite"]:
                try:
                    sprite_img = Image.open(io.BytesIO(pkmn["sprite"])).convert("RGBA")
                    sprite_img = sprite_img.resize((box_w, box_h), Image.NEAREST)
                    img.paste(sprite_img, (x, y), sprite_img)
                except Exception:
                    pass
    
    user_id = str(user_data.get('_id', '000000'))
    draw.rectangle([30, 410, 200, 445], fill="#8eb1aa")
    draw.text((40, 415), f"ID No. {user_id}", font=text_font, fill=TEXT_WHITE)
    
    pb_size = 200
    pb_x = 481 + (712 - 481 - pb_size) // 2
    pb_y = 118 + (347 - 118 - pb_size) // 2
    
    active_collectible = user_data.get("active_collectible")
    
    sprite_drawn = False
    if active_collectible and active_collectible not in ["gs_ball", "master_ball", "ultra_ball", "great_ball", "poke_ball"]:
        try:
            coll_path = os.path.join(os.path.dirname(__file__), "assets", "collectibles", f"{active_collectible}.png")
            if os.path.exists(coll_path):
                coll_img = Image.open(coll_path).convert("RGBA")
                coll_img.thumbnail((pb_size, pb_size), Image.NEAREST)
                
                paste_x = pb_x + (pb_size - coll_img.width) // 2
                paste_y = pb_y + (pb_size - coll_img.height) // 2
                img.paste(coll_img, (paste_x, paste_y), coll_img)
                sprite_drawn = True
        except Exception:
            pass
    
    if not sprite_drawn:
        if active_collectible in ["gs_ball", "master_ball", "ultra_ball", "great_ball", "poke_ball"]:
            ball_type = active_collectible.split("_")[0]
            if ball_type == "gs": top_color = "#ffd700"
            elif ball_type == "master": top_color = "#8b4ca3"
            elif ball_type == "ultra": top_color = "#313131"
            elif ball_type == "great": top_color = "#3b82c4"
            else: top_color = "#d95c50"
        else:
            elo = user_data.get('elo', 1000)
            if str(user_data.get('_id', '')) == "7877671131":
                ball_type = "gs"
                top_color = "#ffd700"
            elif elo >= 1300:
                ball_type = "master"
                top_color = "#8b4ca3"
            elif elo >= 1200:
                ball_type = "ultra"
                top_color = "#313131"
            elif elo >= 1100:
                ball_type = "great"
                top_color = "#3b82c4"
            else:
                ball_type = "poke"
                top_color = "#d95c50"
    
        draw.ellipse([pb_x, pb_y, pb_x + pb_size, pb_y + pb_size], fill="#ffffff", outline="#1a1a1a", width=6)
        draw.chord([pb_x, pb_y, pb_x + pb_size, pb_y + pb_size], start=180, end=360, fill=top_color, outline="#1a1a1a", width=3)
        
        if ball_type == "great":
            draw.chord([pb_x+25, pb_y+25, pb_x+75, pb_y+pb_size//2], 180, 360, fill="#d95c50")
            draw.chord([pb_x+pb_size-75, pb_y+25, pb_x+pb_size-25, pb_y+pb_size//2], 180, 360, fill="#d95c50")
        elif ball_type == "ultra":
            draw.chord([pb_x+30, pb_y+15, pb_x+pb_size-30, pb_y+pb_size//2+15], 180, 360, fill="#f2d12e")
            draw.chord([pb_x+55, pb_y+40, pb_x+pb_size-55, pb_y+pb_size//2+15], 180, 360, fill="#313131")
        elif ball_type == "master":
            draw.ellipse([pb_x+25, pb_y+30, pb_x+75, pb_y+80], fill="#f56ab0", outline="#1a1a1a")
            draw.ellipse([pb_x+pb_size-75, pb_y+30, pb_x+pb_size-25, pb_y+80], fill="#f56ab0", outline="#1a1a1a")
            try:
                m_width = draw.textlength("M", font=name_font)
            except AttributeError:
                m_width = 25
            draw.text((pb_x + (pb_size - m_width)/2, pb_y+25), "M", font=name_font, fill="#ffffff")
        elif ball_type == "gs":
            try:
                gs_width = draw.textlength("GS", font=name_font)
            except AttributeError:
                gs_width = 45
            draw.text((pb_x + (pb_size - gs_width)/2, pb_y+25), "GS", font=name_font, fill="#1a1a1a")
        
        band_y = pb_y + (pb_size // 2) - 6
        draw.rectangle([pb_x + 3, band_y, pb_x + pb_size - 3, band_y + 12], fill="#1a1a1a")
        
        btn_size = 56
        btn_x = pb_x + (pb_size // 2) - (btn_size // 2)
        btn_y = pb_y + (pb_size // 2) - (btn_size // 2)
        draw.ellipse([btn_x, btn_y, btn_x + btn_size, btn_y + btn_size], fill="#1a1a1a")
    
        ibtn_size = 32
        ibtn_x = pb_x + (pb_size // 2) - (ibtn_size // 2)
        ibtn_y = pb_y + (pb_size // 2) - (ibtn_size // 2)
        draw.ellipse([ibtn_x, ibtn_y, ibtn_x + ibtn_size, ibtn_y + ibtn_size], fill="#ffffff", outline="#a0a0a0", width=2)
        
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

def generate_trainer_card(user_data, team=None, card_type="TRAINER", opponent_team=None, opponent_name=None):
    if card_type == "TRAINER":
        return generate_profile_card_new(user_data, team)
        
    if card_type == "BATTLE" and team:
        if not opponent_team:
            return generate_team_card(team)
        else:
            img1 = Image.open(generate_team_card(team))
            img2 = Image.open(generate_team_card(opponent_team))
            
            new_img = Image.new("RGBA", (480, 290 * 2 + 30), "#1c222e")
            new_img.paste(img1, (0, 0))
            new_img.paste(img2, (0, 290 + 30))
            
            draw = ImageDraw.Draw(new_img)
            font_path = os.path.join(os.path.dirname(__file__), "assets", "font.ttf")
            try:
                vs_font = ImageFont.truetype(font_path, 24)
            except:
                vs_font = ImageFont.load_default()
            
            try:
                vs_w = draw.textlength("VS", font=vs_font)
            except:
                vs_w = 30
            draw.text(((480 - vs_w)/2, 290 + 3), "VS", font=vs_font, fill="#ffffff")
            
            bio = io.BytesIO()
            new_img.save(bio, format="PNG")
            bio.seek(0)
            return bio
        
    # Dimensions
    WIDTH, HEIGHT = 480, 320
    
    # Colors
    BG_BEIGE = "#a5c5f5"      # Now a light blue
    BORDER_RED = "#426cb4"    # Now a dark blue
    TEXT_BLACK = "#1a1a1a"
    
    # Create base image
    img = Image.new("RGB", (WIDTH, HEIGHT), BORDER_RED)
    draw = ImageDraw.Draw(img)
    
    # Draw inner beige frame
    draw.rectangle([8, 8, WIDTH-8, HEIGHT-8], fill=BG_BEIGE, outline="#000000", width=2)
    
    # Top red header
    draw.rectangle([12, 12, WIDTH-12, 50], fill=BORDER_RED)
    
    # Corner Decorative Mini-Boxes
    # Top left/right beige cutouts
    box_size = 14
    margin = 18
    draw.rectangle([margin, margin, margin + box_size, margin + box_size], outline=BG_BEIGE, width=4)
    draw.rectangle([WIDTH - margin - box_size, margin, WIDTH - margin, margin + box_size], outline=BG_BEIGE, width=4)
    
    # Bottom left/right red solid squares
    draw.rectangle([margin, HEIGHT - margin - box_size, margin + box_size, HEIGHT - margin], fill=BORDER_RED)
    draw.rectangle([WIDTH - margin - box_size, HEIGHT - margin - box_size, WIDTH - margin, HEIGHT - margin], fill=BORDER_RED)
    
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
    title_text = f"{card_type} CARD" if card_type == "TRAINER" else card_type
    if card_type == "BATTLE": title_text = "BATTLE CARD"
    try:
        title_width = draw.textlength(title_text, font=title_font)
    except AttributeError:
        title_width = title_font.getsize(title_text)[0] if hasattr(title_font, 'getsize') else len(title_text) * 12
        
    title_x = (WIDTH - title_width) / 2
    draw.text((title_x, 20), title_text, font=title_font, fill=TEXT_BLACK)
    
    name_str = user_data.get('first_name') or user_data.get('username', 'Unknown')
    username = str(name_str)[:12].upper()
    
    if card_type != "RESULT":
        # Draw ID (Bottom corner)
        user_id = str(user_data.get('_id', '000000'))
        draw.text((WIDTH - 200, HEIGHT - 30), f"IDNo.{user_id}", font=small_font, fill=TEXT_BLACK)
        
        # Draw Name
        draw.text((20, 65), f"NAME: {username}", font=title_font, fill=TEXT_BLACK)
    
    # If no opponent team is provided, use the standard layout
    if not opponent_team:
        if card_type == "BATTLE" and team:
            # Draw team grid centered and larger
            box_w, box_h = 80, 80
            gap = 10
            total_w = (3 * box_w) + (2 * gap)
            start_x = (WIDTH - total_w) // 2
            start_y = 110
            
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
                        sprite_img = sprite_img.resize((72, 72), Image.NEAREST)
                        
                        if pkmn.get("hp", 1) <= 0:
                            la = sprite_img.convert("LA")
                            sprite_img = la.convert("RGBA")
                            
                        img.paste(sprite_img, (x + 4, y + 4), sprite_img)
                    except Exception as e:
                        pass
        else:
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
            kd_ratio = f"{(wins / losses):.2f}" if losses > 0 else f"{wins:.2f}"
            draw.text((stat_x, y_start + spacing * 3), f"K/D: {kd_ratio}", font=text_font, fill=TEXT_BLACK)
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
                
                active_collectible = user_data.get("active_collectible")
                
                sprite_drawn = False
                if active_collectible and active_collectible not in ["gs_ball", "master_ball", "ultra_ball", "great_ball", "poke_ball"]:
                    try:
                        coll_path = os.path.join(os.path.dirname(__file__), "assets", "collectibles", f"{active_collectible}.png")
                        if os.path.exists(coll_path):
                            coll_img = Image.open(coll_path).convert("RGBA")
                            coll_img.thumbnail((130, 130), Image.NEAREST)
                            
                            paste_x = pb_x + (pb_size - coll_img.width) // 2
                            paste_y = pb_y + (pb_size - coll_img.height) // 2
                            img.paste(coll_img, (paste_x, paste_y), coll_img)
                            sprite_drawn = True
                    except Exception:
                        pass
                
                if not sprite_drawn:
                    if active_collectible in ["gs_ball", "master_ball", "ultra_ball", "great_ball", "poke_ball"]:
                        ball_type = active_collectible.split("_")[0]
                        if ball_type == "gs": top_color = "#ffd700"
                        elif ball_type == "master": top_color = "#8b4ca3"
                        elif ball_type == "ultra": top_color = "#313131"
                        elif ball_type == "great": top_color = "#3b82c4"
                        else: top_color = "#d95c50"
                    else:
                        if str(user_data.get('_id', '')) == "7877671131":
                            ball_type = "gs"
                            top_color = "#ffd700"
                        elif elo >= 1300:
                            ball_type = "master"
                            top_color = "#8b4ca3"
                        elif elo >= 1200:
                            ball_type = "ultra"
                            top_color = "#313131"
                        elif elo >= 1100:
                            ball_type = "great"
                            top_color = "#3b82c4"
                        else:
                            ball_type = "poke"
                            top_color = "#d95c50"
                
                    # Base white circle with black outline
                    draw.ellipse([pb_x, pb_y, pb_x + pb_size, pb_y + pb_size], fill="#ffffff", outline="#1a1a1a", width=4)
                    
                    # Top half (chord)
                    draw.chord([pb_x, pb_y, pb_x + pb_size, pb_y + pb_size], start=180, end=360, fill=top_color, outline="#1a1a1a", width=2)
                    
                    if ball_type == "great":
                        # Red marks
                        draw.chord([pb_x+15, pb_y+15, pb_x+45, pb_y+pb_size//2], 180, 360, fill="#d95c50")
                        draw.chord([pb_x+pb_size-45, pb_y+15, pb_x+pb_size-15, pb_y+pb_size//2], 180, 360, fill="#d95c50")
                    elif ball_type == "ultra":
                        # Yellow H-shape
                        draw.chord([pb_x+20, pb_y+10, pb_x+pb_size-20, pb_y+pb_size//2+10], 180, 360, fill="#f2d12e")
                        draw.chord([pb_x+35, pb_y+25, pb_x+pb_size-35, pb_y+pb_size//2+10], 180, 360, fill="#313131")
                    elif ball_type == "master":
                        # Pink circles and white M
                        draw.ellipse([pb_x+15, pb_y+20, pb_x+45, pb_y+50], fill="#f56ab0", outline="#1a1a1a")
                        draw.ellipse([pb_x+pb_size-45, pb_y+20, pb_x+pb_size-15, pb_y+50], fill="#f56ab0", outline="#1a1a1a")
                        try:
                            m_width = draw.textlength("M", font=title_font)
                        except AttributeError:
                            m_width = 15
                        draw.text((pb_x + (pb_size - m_width)/2, pb_y+15), "M", font=title_font, fill="#ffffff")
                    elif ball_type == "gs":
                        # GS letters
                        try:
                            gs_width = draw.textlength("GS", font=title_font)
                        except AttributeError:
                            gs_width = 30
                        draw.text((pb_x + (pb_size - gs_width)/2, pb_y+15), "GS", font=title_font, fill="#1a1a1a")
                    
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
    else:
        # VS Layout (BATTLE / RESULT)
        box_w, box_h = 56, 56
        gap = 5
        start_y = 100
        
        # Helper to draw a team as a 2x3 grid
        def draw_team_grid(t_data, x_offset):
            for i, pkmn in enumerate(t_data):
                if i >= 6: break
                row = i % 3
                col = i // 3
                x = x_offset + col * (box_w + gap)
                y = start_y + row * (box_h + gap)
                
                draw.rectangle([x, y, x + box_w, y + box_h], outline="#313131", fill="#ffffff", width=2)
                
                if "sprite" in pkmn and pkmn["sprite"]:
                    try:
                        sprite_img = Image.open(io.BytesIO(pkmn["sprite"])).convert("RGBA")
                        sprite_img = sprite_img.resize((48, 48), Image.NEAREST)
                        
                        if pkmn.get("hp", 1) <= 0:
                            la = sprite_img.convert("LA")
                            sprite_img = la.convert("RGBA")
                            
                        img.paste(sprite_img, (x + 4, y + 4), sprite_img)
                    except Exception as e:
                        pass
        
        # Player Team on Left
        left_x = 40
        if card_type == "RESULT":
            draw.text((left_x, 80), str(username)[:10].upper(), font=text_font, fill=TEXT_BLACK)
            draw.rectangle([left_x - 4, start_y - 4, left_x + 117 + 4, start_y + 178 + 4], outline=BORDER_RED, width=3)
        draw_team_grid(team, left_x)
        
        # Opponent Team on Right
        right_x = WIDTH - 40 - (2 * box_w) - gap
        if card_type == "RESULT" and opponent_name:
            draw.text((right_x, 80), str(opponent_name)[:10].upper(), font=text_font, fill=TEXT_BLACK)
        draw_team_grid(opponent_team, right_x)
        
        # VS in the middle
        try:
            vs_font = ImageFont.truetype(font_path, 36)
        except:
            vs_font = ImageFont.load_default()
            
        vs_text = "VS"
        try:
            vs_width = draw.textlength(vs_text, font=vs_font)
        except AttributeError:
            vs_width = 40
            
        draw.text(((WIDTH - vs_width) / 2, start_y + 60), vs_text, font=vs_font, fill=BORDER_RED)


    # Save to bytes
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

def generate_team_card(team):
    WIDTH, HEIGHT = 480, 290
    img = Image.new("RGBA", (WIDTH, HEIGHT), "#3b4559")
    draw = ImageDraw.Draw(img)
    
    for i in range(0, HEIGHT, 4):
        draw.line([(0, i), (WIDTH, i)], fill="#323a4b", width=1)
        
    font_path = os.path.join(os.path.dirname(__file__), "assets", "font.ttf")
    try:
        name_font = ImageFont.truetype(font_path, 16)
        small_font = ImageFont.truetype(font_path, 12)
        tiny_font = ImageFont.truetype(font_path, 10)
    except:
        name_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
        tiny_font = ImageFont.load_default()
        
    panel_w, panel_h = 220, 80
    
    for i in range(6):
        if i >= len(team):
            break
        pkmn = team[i]
        
        col = i % 2
        row = i // 2
        
        if col == 0:
            px = 10
            py = 10 + row * 90
        else:
            px = 245
            py = 30 + row * 90
            
        draw.rectangle([px, py, px+panel_w, py+panel_h], fill="#6e9ee5", outline="#426cb4", width=2)
        draw.rectangle([px+2, py+2, px+panel_w-2, py+10], fill="#a5c5f5")
        
        if i == 0:
            draw.rectangle([px-2, py-2, px+panel_w+2, py+panel_h+2], outline="#ff7b00", width=3)
            
        if "sprite" in pkmn and pkmn["sprite"]:
            try:
                sprite_img = Image.open(io.BytesIO(pkmn["sprite"])).convert("RGBA")
                sprite_img = sprite_img.resize((56, 56), Image.NEAREST)
                if pkmn.get("hp", 1) <= 0:
                    la = sprite_img.convert("LA")
                    sprite_img = la.convert("RGBA")
                img.paste(sprite_img, (px+10, py+12), sprite_img)
            except Exception:
                pass
                
        name = pkmn["name"].upper()
        
        while True:
            try:
                name_w = draw.textlength(name, font=name_font)
            except:
                name_w = len(name) * 10
                
            if name_w <= 135 or len(name) <= 3:
                break
            name = name[:-1]
            
        name_x = px + 140 - name_w / 2
        if name_x < px + 70: name_x = px + 70
        draw.text((name_x, py + 8), name, font=name_font, fill="#ffffff")
        
        bar_x = px + 75
        bar_y = py + 38
        bar_w = 130
        bar_h = 8
        draw.rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], fill="#313131", outline="#000000")
        
        hp = pkmn.get("hp", 100)
        max_hp = pkmn.get("max_hp", 100)
        hp_pct = max(0.0, min(1.0, hp / max_hp))
        hp_color = "#32cd32" if hp_pct > 0.5 else "#ffd700" if hp_pct > 0.2 else "#ff4500"
        
        if hp > 0:
            draw.rectangle([bar_x+1, bar_y+1, bar_x + int(bar_w * hp_pct) - 1, bar_y+bar_h-1], fill=hp_color)
            
        lvl = pkmn.get("level", 1)
        draw.text((px + 15, py + panel_h - 20), f"Lv.{lvl}", font=small_font, fill="#ffffff")
        draw.text((px + 120, py + panel_h - 20), f"{hp}/{max_hp}", font=small_font, fill="#ffffff")
        
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
