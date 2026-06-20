from motor.motor_asyncio import AsyncIOMotorClient
import config

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(config.MONGO_URI)
        self.db = self.client[config.DB_NAME]
        self.users = self.db.users
        self.pokemon = self.db.pokemon

    async def get_user(self, user_id: int):
        return await self.users.find_one({"_id": user_id})

    async def create_user(self, user_id: int, username: str):
        user = {
            "_id": user_id,
            "username": username,
            "balance": 1000,
            "party": [],
            "pc": [],
            "battles_played": 0,
            "wins": 0,
            "losses": 0,
            "elo": 1000,
            "total_damage": 0
        }
        await self.users.insert_one(user)
        return user

    async def update_battle_stats(self, user_id: int, won: bool, damage_dealt: int, elo_change: int):
        # Use $inc to atomically increment stats
        inc_data = {
            "battles_played": 1,
            "total_damage": damage_dealt,
            "elo": elo_change
        }
        if won:
            inc_data["wins"] = 1
        else:
            inc_data["losses"] = 1
            
        await self.users.update_one(
            {"_id": user_id},
            {"$inc": inc_data}
        )

db = Database()
