import json
import os

LEADERBOARD_FILE = os.path.join(os.path.dirname(__file__), 'data', 'leaderboard.json')

def load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE):
        return {}
    try:
        with open(LEADERBOARD_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_leaderboard(data):
    # Ensure dir exists
    os.makedirs(os.path.dirname(LEADERBOARD_FILE), exist_ok=True)
    with open(LEADERBOARD_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def add_win(user_id, username):
    data = load_leaderboard()
    uid_str = str(user_id)
    if uid_str not in data:
        data[uid_str] = {"username": username, "wins": 0}
    
    # Update username in case they changed it
    data[uid_str]["username"] = username
    data[uid_str]["wins"] += 1
    
    save_leaderboard(data)

def get_top_players(limit=10):
    data = load_leaderboard()
    players = list(data.values())
    players.sort(key=lambda x: x['wins'], reverse=True)
    return players[:limit]
