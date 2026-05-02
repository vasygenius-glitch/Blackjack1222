import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH", "firebase-key.json")
CREATOR_USERNAME = os.getenv("CREATOR_USERNAME", "z_1l1")
try:
    CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))
except ValueError:
    CREATOR_ID = 0
