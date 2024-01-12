from pymongo import MongoClient
from typing import List


class DatabaseManager:
    def __init__(self, uri: str, db_name: str, collection_name: str):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def insert(self, data: dict):
        return self.collection.insert_one(data)

    def update_queue(self, guild_id: str, tracks_dict: dict):
        return self.collection.update_one(
            {"guildId": guild_id}, {"$set": tracks_dict}, upsert=True
        )

    def get_queue(self, guild_id: str):
        doc = self.collection.find_one({"guildId": guild_id})
        return doc["queue"] if doc else []

    def delete_queue(self, guild_id: str):
        return self.collection.delete_one({"guildId": guild_id})
