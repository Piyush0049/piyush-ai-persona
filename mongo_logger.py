"""MongoDB Logger - Logs all chat messages for review"""
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

class MongoLogger:
    def __init__(self):
        self.enabled = False
        self.client = None
        self.db = None
        self.collection = None

        mongo_uri = os.environ.get("MONGODB_URI", "")

        if mongo_uri:
            try:
                self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
                self.client.admin.command('ping')
                db_name = os.environ.get("MONGODB_DATABASE", "rag_chat_logs")
                self.db = self.client[db_name]
                self.collection = self.db["messages"]
                self.enabled = True
                print(f"[OK] MongoDB logging enabled: {db_name}.messages")
            except (ConnectionFailure, OperationFailure) as e:
                print(f"[WARN] MongoDB connection failed: {e}")
                print("[INFO] Continuing without message logging")
                self.enabled = False
        else:
            print("[INFO] MongoDB not configured - message logging disabled")

    def log_message(
        self,
        message: str,
        response: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.enabled:
            return False

        try:
            document = {
                "timestamp": datetime.utcnow(),
                "message": message,
                "response": response,
                "session_id": session_id,
                "metadata": metadata or {}
            }
            self.collection.insert_one(document)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to log message: {e}")
            return False

    def get_recent_messages(self, limit: int = 100) -> list:
        if not self.enabled:
            return []
        try:
            return list(self.collection.find().sort("timestamp", -1).limit(limit))
        except Exception as e:
            print(f"[ERROR] Failed to fetch messages: {e}")
            return []

    def get_messages_by_session(self, session_id: str) -> list:
        if not self.enabled:
            return []
        try:
            return list(self.collection.find({"session_id": session_id}).sort("timestamp", 1))
        except Exception as e:
            print(f"[ERROR] Failed to fetch session messages: {e}")
            return []

mongo_logger = MongoLogger()
