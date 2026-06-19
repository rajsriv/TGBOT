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
            "pc": []
        }
        await self.users.insert_one(user)
        return user

db = Database()
