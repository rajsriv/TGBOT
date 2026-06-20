import random

NATURES = ["Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed", "Impish", "Lax", "Timid", "Hasty", "Serious", "Jolly", "Naive", "Modest", "Mild", "Quiet", "Bashful", "Rash", "Calm", "Gentle", "Sassy", "Careful", "Quirky"]

def calc_stat(base: int, iv: int, ev: int, level: int, nature_mod: float = 1.0, is_hp: bool = False) -> int:
    if is_hp:
        return int(((2 * base + iv + ev // 4) * level) / 100) + level + 10
    return int((((2 * base + iv + ev // 4) * level) / 100 + 5) * nature_mod)

def roll_ivs() -> dict:
    stats = ["hp", "atk", "def", "sp_atk", "sp_def", "spd"]
    return {s: random.randint(0, 31) for s in stats}

def get_stat_multiplier(stage: int) -> float:
    stage = max(-6, min(6, stage))
    if stage >= 0:
        return (2 + stage) / 2.0
    return 2.0 / (2 - stage)

BALL_RATES = { "pokeball": 1, "greatball": 1.5, "ultraball": 2, "masterball": 255 }

def catch_chance(pokemon_catch_rate: int, ball_modifier: float, hp_max: int, hp_current: int, status: float = 1.0) -> bool:
    a = ((3 * hp_max - 2 * hp_current) * pokemon_catch_rate * ball_modifier * status) / (3 * hp_max)
    if a >= 255:
        return True
    b = 65536 / ((255 / a) ** 0.1875)
    return all(random.randint(0, 65535) < b for _ in range(4))
