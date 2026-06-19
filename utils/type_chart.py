TYPE_CHART = {
    "normal": {
        "2": [],
        "0.5": [
            "rock",
            "steel"
        ],
        "0": [
            "ghost"
        ]
    },
    "fighting": {
        "2": [
            "normal",
            "rock",
            "steel",
            "ice",
            "dark"
        ],
        "0.5": [
            "flying",
            "poison",
            "bug",
            "psychic",
            "fairy"
        ],
        "0": [
            "ghost"
        ]
    },
    "flying": {
        "2": [
            "fighting",
            "bug",
            "grass"
        ],
        "0.5": [
            "rock",
            "steel",
            "electric"
        ],
        "0": []
    },
    "poison": {
        "2": [
            "grass",
            "fairy"
        ],
        "0.5": [
            "poison",
            "ground",
            "rock",
            "ghost"
        ],
        "0": [
            "steel"
        ]
    },
    "ground": {
        "2": [
            "poison",
            "rock",
            "steel",
            "fire",
            "electric"
        ],
        "0.5": [
            "bug",
            "grass"
        ],
        "0": [
            "flying"
        ]
    },
    "rock": {
        "2": [
            "flying",
            "bug",
            "fire",
            "ice"
        ],
        "0.5": [
            "fighting",
            "ground",
            "steel"
        ],
        "0": []
    },
    "bug": {
        "2": [
            "grass",
            "psychic",
            "dark"
        ],
        "0.5": [
            "fighting",
            "flying",
            "poison",
            "ghost",
            "steel",
            "fire",
            "fairy"
        ],
        "0": []
    },
    "ghost": {
        "2": [
            "ghost",
            "psychic"
        ],
        "0.5": [
            "dark"
        ],
        "0": [
            "normal"
        ]
    },
    "steel": {
        "2": [
            "rock",
            "ice",
            "fairy"
        ],
        "0.5": [
            "steel",
            "fire",
            "water",
            "electric"
        ],
        "0": []
    },
    "fire": {
        "2": [
            "bug",
            "steel",
            "grass",
            "ice"
        ],
        "0.5": [
            "rock",
            "fire",
            "water",
            "dragon"
        ],
        "0": []
    },
    "water": {
        "2": [
            "ground",
            "rock",
            "fire"
        ],
        "0.5": [
            "water",
            "grass",
            "dragon"
        ],
        "0": []
    },
    "grass": {
        "2": [
            "ground",
            "rock",
            "water"
        ],
        "0.5": [
            "flying",
            "poison",
            "bug",
            "steel",
            "fire",
            "grass",
            "dragon"
        ],
        "0": []
    },
    "electric": {
        "2": [
            "flying",
            "water"
        ],
        "0.5": [
            "grass",
            "electric",
            "dragon"
        ],
        "0": [
            "ground"
        ]
    },
    "psychic": {
        "2": [
            "fighting",
            "poison"
        ],
        "0.5": [
            "steel",
            "psychic"
        ],
        "0": [
            "dark"
        ]
    },
    "ice": {
        "2": [
            "flying",
            "ground",
            "grass",
            "dragon"
        ],
        "0.5": [
            "steel",
            "fire",
            "water",
            "ice"
        ],
        "0": []
    },
    "dragon": {
        "2": [
            "dragon"
        ],
        "0.5": [
            "steel"
        ],
        "0": [
            "fairy"
        ]
    },
    "dark": {
        "2": [
            "ghost",
            "psychic"
        ],
        "0.5": [
            "fighting",
            "dark",
            "fairy"
        ],
        "0": []
    },
    "fairy": {
        "2": [
            "fighting",
            "dragon",
            "dark"
        ],
        "0.5": [
            "poison",
            "steel",
            "fire"
        ],
        "0": []
    }
}

def get_type_multiplier(move_type, defender_types):
    if move_type not in TYPE_CHART:
        return 1.0
    mod = 1.0
    for dt in defender_types:
        if dt in TYPE_CHART[move_type]["2"]:
            mod *= 2.0
        elif dt in TYPE_CHART[move_type]["0.5"]:
            mod *= 0.5
        elif dt in TYPE_CHART[move_type]["0"]:
            mod *= 0.0
    return mod
