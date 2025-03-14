import aiosqlite
import logging
import os
from datetime import datetime
import requests
from tenacity import retry, stop_after_attempt, wait_fixed

# Constants
DATABASE_PATH = "verification_bot.db"
LEGISLATOR_API_URL = "https://data.ct.gov/resource/rgw6-bpst.json"

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    """Initializes the SQLite database and required tables."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS legislators (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            full_name TEXT UNIQUE NOT NULL,
                            role TEXT NOT NULL CHECK(role IN ('Senator', 'Representative'))
                          )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS verification_requests (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT UNIQUE NOT NULL,
                            discord_username TEXT NOT NULL,
                            legislator_name TEXT NOT NULL,
                            role TEXT NOT NULL,
                            status TEXT NOT NULL CHECK(status IN ('Pending', 'Approved', 'Denied')),
                            request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                          )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS registered_users (
                            user_id TEXT PRIMARY KEY,
                            discord_username TEXT NOT NULL,
                            legislator_name TEXT NOT NULL,
                            role TEXT NOT NULL,
                            assigned_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                          )''')
        
        await db.commit()
        logger.info("Database initialized successfully.")

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_legislator_data():
    """Fetch legislator data from the API with retry logic."""
    response = requests.get(LEGISLATOR_API_URL, timeout=10)
    response.raise_for_status()
    return response.json()

async def update_legislators():
    """Fetches and updates legislators from the API."""
    try:
        data = fetch_legislator_data()
        legislators = [(entry["full_name"], entry["role"]) for entry in data]
        
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.executemany("INSERT OR REPLACE INTO legislators (full_name, role) VALUES (?, ?)", legislators)
            await db.commit()
            logger.info("Legislator database updated successfully.")
    except Exception as e:
        logger.error(f"Failed to update legislators: {e}")
