import json
import random
import os
import uuid
import leaderboard

# Load heroes
HEROES_FILE = os.path.join(os.path.dirname(__file__), 'data', 'heroes.json')
try:
    with open(HEROES_FILE, 'r') as f:
        HEROES_DB = json.load(f)
except FileNotFoundError:
    HEROES_DB = []

def get_random_team(size=3):
    team = random.sample(HEROES_DB, min(size, len(HEROES_DB)))
    total_hp = sum(hero['hp_max'] for hero in team)
    return team, total_hp

class GameManager:
    def __init__(self):
        # matches[match_id] = { player_data... }
        self.matches = {}
        # Simple lookup to prevent multiple duals: user_id -> match_id
        self.active_players = {}

    def create_match(self, p1_id, p1_name, p2_id, p2_name):
        match_id = str(uuid.uuid4())
        
        p1_team, p1_hp = get_random_team()
        p2_team, p2_hp = get_random_team()
        
        match = {
            "match_id": match_id,
            "p1_id": p1_id,
            "p1_name": p1_name,
            "p2_id": p2_id,
            "p2_name": p2_name,
            "p1_hp": p1_hp,
            "p1_max_hp": p1_hp,
            "p2_hp": p2_hp,
            "p2_max_hp": p2_hp,
            "p1_team": p1_team,
            "p2_team": p2_team,
            "current_turn": p1_id, # p1 goes first
            "status": "ACTIVE",
            "log": "Battle started!",
            "winner": None
        }
        
        self.matches[match_id] = match
        self.active_players[p1_id] = match_id
        self.active_players[p2_id] = match_id
        return match

    def get_match(self, match_id):
        return self.matches.get(match_id)
        
    def end_match(self, match_id):
        if match_id in self.matches:
            match = self.matches[match_id]
            match['status'] = "FINISHED"
            if match['p1_id'] in self.active_players:
                del self.active_players[match['p1_id']]
            if match['p2_id'] in self.active_players:
                del self.active_players[match['p2_id']]

    def process_move(self, match_id, player_id, move_type):
        """
        Process a move. Returns (success_bool, message)
        """
        match = self.get_match(match_id)
        if not match or match['status'] != 'ACTIVE':
            return False, "Match is not active."
            
        if match['current_turn'] != player_id:
            return False, "It is not your turn!"
            
        # Identify attacker and defender
        is_p1 = (player_id == match['p1_id'])
        attacker_team = match['p1_team'] if is_p1 else match['p2_team']
        defender_id = match['p2_id'] if is_p1 else match['p1_id']
        attacker_name = match['p1_name'] if is_p1 else match['p2_name']
        defender_name = match['p2_name'] if is_p1 else match['p1_name']
        attacker_hp = match['p1_hp'] if is_p1 else match['p2_hp']
        attacker_max_hp = match['p1_max_hp'] if is_p1 else match['p2_max_hp']
        
        # Stats based on teams
        avg_atk = sum(h['atk_base'] for h in attacker_team) / len(attacker_team)
        defender_team = match['p2_team'] if is_p1 else match['p1_team']
        avg_dex = sum(h['dex'] for h in defender_team) / len(defender_team)
        avg_crt = sum(h['crt'] for h in attacker_team) / len(attacker_team)
        
        # Move logic
        multiplier = 1.0
        accuracy = 1.0
        if move_type == 'quick':
            multiplier = 1.0
            accuracy = 1.0
        elif move_type == 'power':
            multiplier = 1.7
            accuracy = 0.7
        elif move_type == 'ultimate':
            if attacker_hp > attacker_max_hp * 0.3:
                return False, "Ultimate is only available when HP < 30%!"
            multiplier = 3.0
            accuracy = 0.4
            
        # Accuracy check
        if random.random() > accuracy:
            match['log'] = f"💨 {attacker_name} used {move_type.title()} Attack but **MISSED**!"
            match['current_turn'] = defender_id
            return True, "Missed!"
            
        # Dodge check
        if random.random() < avg_dex:
            match['log'] = f"🍃 {attacker_name} used {move_type.title()} Attack, but {defender_name} **DODGED**!"
            match['current_turn'] = defender_id
            return True, "Dodged!"
            
        # Crit check
        is_crit = random.random() < avg_crt
        crit_mult = 2.0 if is_crit else 1.0
        
        # Calculate Damage
        damage = int((avg_atk * multiplier) * crit_mult)
        
        # Apply damage
        if is_p1:
            match['p2_hp'] = max(0, match['p2_hp'] - damage)
            hp_left = match['p2_hp']
        else:
            match['p1_hp'] = max(0, match['p1_hp'] - damage)
            hp_left = match['p1_hp']
            
        crit_msg = "💥 **CRITICAL HIT!** " if is_crit else ""
        match['log'] = f"⚔️ {attacker_name} used {move_type.title()} Attack and dealt **{damage}** DMG!\n{crit_msg}"
        
        # Check Win
        if hp_left <= 0:
            match['winner'] = player_id
            match['log'] += f"\n\n🏆 {attacker_name} wins the duel!"
            self.end_match(match_id)
            leaderboard.add_win(player_id, attacker_name)
        else:
            match['current_turn'] = defender_id
            
        return True, "Move processed"

# Global GM instance
game_manager = GameManager()
