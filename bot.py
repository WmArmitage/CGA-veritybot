import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import os
import requests
import asyncio
import datetime

# Constants
ADMIN_ROLE_ID = 1242292827510276269
APPROVAL_CHANNEL_ID = 1242300716119494806
SENATOR_ROLE_ID = 1242296657933107221
REPRESENTATIVE_ROLE_ID = 1242296757954674758
CGA_STAFF_ROLE_ID = 1244067941662720061
PRESS_ROLE_ID = 1242989393049030727
GUILD_ID = 1242198415547433030
AUDIT_LOG_CHANNEL_ID = 1347258435452014703
LEGISLATOR_API_URL = "https://data.ct.gov/resource/rgw6-bpst.json"
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")  # Ensure the API key is stored securely


# Bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# Database setup
def init_db():
    conn = sqlite3.connect("verification_bot.db")
    cursor = conn.cursor()
    
    # Legislators table (Synced from API)
    cursor.execute('''CREATE TABLE IF NOT EXISTS legislators (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        full_name TEXT UNIQUE NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('Senator', 'Representative'))
                      )''')
    
    # Verification Requests (Tracks pending requests)
    cursor.execute('''CREATE TABLE IF NOT EXISTS verification_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT UNIQUE NOT NULL,
                        discord_username TEXT NOT NULL,
                        legislator_name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('Pending', 'Approved', 'Denied')),
                        request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                      )''')
    
    # Registered Users (Tracks assigned roles)
    cursor.execute('''CREATE TABLE IF NOT EXISTS registered_users (
                        user_id TEXT PRIMARY KEY,
                        discord_username TEXT NOT NULL,
                        legislator_name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        assigned_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                      )''')
    
    conn.commit()
    conn.close()

# API Sync
def fetch_legislators():
    API_URL = "https://data.ct.gov/resource/rgw6-bpst.json"
    API_TOKEN = os.getenv("API_TOKEN")  # Read from Railway variables
    
    headers = {"X-App-Token": API_TOKEN}
    response = requests.get(API_URL, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        update_legislators(data)
    else:
        print("Failed to fetch legislators: ", response.status_code)

def update_legislators(data):
    conn = sqlite3.connect("verification_bot.db")
    cursor = conn.cursor()
    
    # Store current legislators before update
    cursor.execute("SELECT full_name FROM legislators")
    existing_legislators = {row[0] for row in cursor.fetchall()}
    
    new_legislators = set()
    for entry in data:
        full_name = entry.get("name", "").strip()
        role = entry.get("title", "").strip()
        
        if full_name and role in ("Senator", "Representative"):
            new_legislators.add(full_name)
            cursor.execute("INSERT OR IGNORE INTO legislators (full_name, role) VALUES (?, ?)", (full_name, role))
    
    # Remove legislators who are no longer in the API
    removed_legislators = existing_legislators - new_legislators
    for legislator in removed_legislators:
        cursor.execute("DELETE FROM legislators WHERE full_name = ?", (legislator,))
        print(f"Removed {legislator} (No longer in API)")  # Notify admin here
    
    conn.commit()
    conn.close()

# Run database setup
init_db()
fetch_legislators()




# VERIFICATION REQUEST HANDLING

@bot.tree.command(name="senator")
async def senator(ctx, name: str):
    with sqlite3.connect("verification_bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT full_name FROM legislators WHERE full_name = ?", (name,))
        if not cursor.fetchone():
            await ctx.respond("Invalid legislator name. Please use the correct full name.")
            return
        cursor.execute("SELECT * FROM verification_requests WHERE user_id = ?", (ctx.author.id,))
        if cursor.fetchone():
            await ctx.respond("You already have a pending request.")
            return
        cursor.execute("INSERT INTO verification_requests (user_id, discord_username, legislator_name, role, status) VALUES (?, ?, ?, ?, ?)",
                       (ctx.author.id, ctx.author.name, name, "Senator", "Pending"))
        conn.commit()
        await ctx.respond(f"Request submitted for {name} as Senator.")

@bot.tree.command(name="representative")
async def representative(ctx, name: str):
    with sqlite3.connect("verification_bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT full_name FROM legislators WHERE full_name = ?", (name,))
        if not cursor.fetchone():
            await ctx.respond("Invalid legislator name. Please use the correct full name.")
            return
        cursor.execute("SELECT * FROM verification_requests WHERE user_id = ?", (ctx.author.id,))
        if cursor.fetchone():
            await ctx.respond("You already have a pending request.")
            return
        cursor.execute("INSERT INTO verification_requests (user_id, discord_username, legislator_name, role, status) VALUES (?, ?, ?, ?, ?)",
                       (ctx.author.id, ctx.author.name, name, "Representative", "Pending"))
        conn.commit()
        await ctx.respond(f"Request submitted for {name} as Representative.")

@bot.tree.command(name="cgastaff")
async def cgastaff(ctx):
    with sqlite3.connect("verification_bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM verification_requests WHERE user_id = ?", (ctx.author.id,))
        if cursor.fetchone():
            await ctx.respond("You already have a pending request.")
            return
        cursor.execute("INSERT INTO verification_requests (user_id, discord_username, legislator_name, role, status) VALUES (?, ?, ?, ?, ?)",
                       (ctx.author.id, ctx.author.name, "N/A", "CGA Staff", "Pending"))
        conn.commit()
        await ctx.respond("Request submitted for CGA Staff.")

@bot.tree.command(name="pressmedia")
async def pressmedia(ctx):
    with sqlite3.connect("verification_bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM verification_requests WHERE user_id = ?", (ctx.author.id,))
        if cursor.fetchone():
            await ctx.respond("You already have a pending request.")
            return
        cursor.execute("INSERT INTO verification_requests (user_id, discord_username, legislator_name, role, status) VALUES (?, ?, ?, ?, ?)",
                       (ctx.author.id, ctx.author.name, "N/A", "Press/Media", "Pending"))
        conn.commit()
        await ctx.respond("Request submitted for Press/Media.")
        return
    cursor.execute("INSERT INTO verification_requests (user_id, discord_name, role_requested, legislator_name, status) VALUES (?, ?, ?, ?, ?)",
                   (ctx.author.id, ctx.author.name, "Press/Media", "N/A", "Pending"))
    conn.commit()
    await ctx.respond("Request submitted for Press/Media.")

#ADMIN APPROVAL SYSTEM


def get_pending_requests():
    """Fetch all pending verification requests."""
    cursor.execute("SELECT id, user_id, username, role_requested, legislator_name, request_time FROM verification_requests WHERE status = 'pending'")
    return cursor.fetchall()

def approve_request(request_id):
    """Approve a verification request and assign the role."""
    cursor.execute("UPDATE verification_requests SET status = 'approved' WHERE id = ?", (request_id,))
    conn.commit()
    return True

def deny_request(request_id):
    """Deny a verification request."""
    cursor.execute("UPDATE verification_requests SET status = 'denied' WHERE id = ?", (request_id,))
    conn.commit()
    return True

def expire_old_requests():
    """Automatically expire requests that are older than 24 hours."""
    expiration_time = datetime.utcnow() - timedelta(hours=24)
    cursor.execute("UPDATE verification_requests SET status = 'expired' WHERE status = 'pending' AND request_time < ?", (expiration_time,))
    conn.commit()
    return True

# Command for admins to check pending requests
@bot.command()
@commands.has_role("Administrator")
async def pending_requests(ctx):
    cursor.execute("SELECT id, username, role_requested, legislator_name FROM requests WHERE status = 'pending'")
    requests = cursor.fetchall()
    
    if not requests:
        await ctx.send("No pending requests.")
        return
    
    message = "**Pending Verification Requests:**\n"
    for req in requests:
        message += f"ID: {req[0]} | User: {req[1]} | Role: {req[2]} | Legislator: {req[3]}\n"
    
    await ctx.send(message)

# Admin approval command
@bot.command()
@commands.has_role("Administrator")
async def approve(ctx, request_id: int):
    cursor.execute("SELECT user_id, role_requested FROM requests WHERE id = ? AND status = 'pending'", (request_id,))
    request = cursor.fetchone()
    
    if not request:
        await ctx.send("Invalid or already processed request ID.")
        return
    
    user = ctx.guild.get_member(request[0])
    role = discord.utils.get(ctx.guild.roles, name=request[1])
    
    if user and role:
        await user.add_roles(role)
        cursor.execute("UPDATE requests SET status = 'approved' WHERE id = ?", (request_id,))
        conn.commit()
        await user.send(f"Your verification request has been approved! You have been assigned the {role.name} role.")
        await ctx.send(f"Approved request {request_id}. {user.mention} has been assigned {role.name}.")
    else:
        await ctx.send("Error: User or role not found.")

# Admin denial command
@bot.command()
@commands.has_role("Administrator")
async def deny(ctx, request_id: int):
    cursor.execute("SELECT user_id FROM requests WHERE id = ? AND status = 'pending'", (request_id,))
    request = cursor.fetchone()
    
    if not request:
        await ctx.send("Invalid or already processed request ID.")
        return
    
    user = ctx.guild.get_member(request[0])
    if user:
        await user.send("Your verification request has been denied. Contact an admin if you believe this is an error.")
    
    cursor.execute("UPDATE requests SET status = 'denied' WHERE id = ?", (request_id,))
    conn.commit()
    await ctx.send(f"Denied request {request_id}.")

# Auto-expiration for old requests
@tasks.loop(minutes=60)
async def expire_requests():
    expiration_time = datetime.utcnow() - timedelta(hours=24)
    cursor.execute("SELECT id, user_id FROM requests WHERE status = 'pending' AND timestamp <= ?", (expiration_time,))
    expired_requests = cursor.fetchall()
    
    for request in expired_requests:
        user = bot.get_user(request[1])
        if user:
            await user.send("Your verification request has expired due to inactivity. Please submit a new request if you still require verification.")
        cursor.execute("DELETE FROM requests WHERE id = ?", (request[0],))
    conn.commit()

    # ROLE LIMIT API

    db.commit()

bot = commands.Bot(command_prefix="/")

def fetch_legislators():
    headers = {"X-App-Token": API_TOKEN}
    response = requests.get(API_URL, headers=headers)
    if response.status_code == 200:
        return response.json()
    return []

@tasks.loop(hours=24)
async def refresh_legislators():
    """Refresh the list of legislators daily."""
    legislators = fetch_legislators()
    cursor.execute("DELETE FROM legislators")  # Clear old data
    for leg in legislators:
        full_name = f"{leg.get('first_name')} {leg.get('last_name')}"
        role = "Senator" if leg.get("chamber") == "Senate" else "Representative"
        cursor.execute("INSERT INTO legislators (full_name, role) VALUES (?, ?) ON CONFLICT(full_name) DO NOTHING", (full_name, role))
    db.commit()

@bot.command()
@commands.has_role("Administrator")
async def refresh_legislators_cmd(ctx):
    """Manually refresh the legislator list."""
    refresh_legislators()
    await ctx.send("Legislator list updated.")

@bot.command()
@commands.has_role("Administrator")
async def legislativestatus(ctx):
    """Show current role count."""
    cursor.execute("SELECT role, COUNT(*) FROM legislators GROUP BY role")
    counts = {row[0]: row[1] for row in cursor.fetchall()}
    senator_count = counts.get("Senator", 0)
    rep_count = counts.get("Representative", 0)
    
    await ctx.send(f"Senators: {senator_count}/36\nRepresentatives: {rep_count}/151")

@bot.command()
async def request_role(ctx, role: str, first_name: str, last_name: str):
    """Request a role (Senator/Representative) by providing a first and last name."""
    full_name = f"{first_name} {last_name}"
    cursor.execute("SELECT role FROM legislators WHERE full_name = ?", (full_name,))
    result = cursor.fetchone()
    
    if result and result[0] == role:
        await ctx.send(f"{full_name} is verified as a {role}. Your request has been sent to the admins.")
        # Send request for admin approval (implementation in another module)
    else:
        await ctx.send(f"Error: {full_name} is not listed as a {role}.")

refresh_legislators.start()

# Function to check if user already has a role
def user_has_role(discord_id):
    cursor.execute("SELECT role FROM verified_users WHERE discord_id = ?", (discord_id,))
    return cursor.fetchone()

# Slash command to request a role
@bot.command()
async def senator(ctx, name: str):
    if user_has_role(ctx.author.id):
        await ctx.send("You already have a verified role. Contact an admin if this is an error.")
        return
    
    # Send request to admin channel
    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    await admin_channel.send(f"New Senator request: {name} from {ctx.author.mention}")

@bot.command()
async def representative(ctx, name: str):
    if user_has_role(ctx.author.id):
        await ctx.send("You already have a verified role. Contact an admin if this is an error.")
        return
    
    # Send request to admin channel
    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    await admin_channel.send(f"New Representative request: {name} from {ctx.author.mention}")

# Auto-remove users whose names are no longer in the API
@tasks.loop(hours=24)
async def check_legislators():
    response = requests.get(API_URL, headers={"X-App-Token": API_TOKEN})
    if response.status_code != 200:
        print("Failed to fetch API data")
        return

    data = response.json()
    current_legislators = {f"{entry['first_name']} {entry['last_name']}" for entry in data}

    cursor.execute("SELECT discord_id, legislator_name FROM verified_users")
    for discord_id, legislator_name in cursor.fetchall():
        if legislator_name not in current_legislators:
            # Remove the role
            user = bot.get_user(discord_id)
            if user:
                member = discord.utils.get(ctx.guild.members, id=discord_id)
                if member:
                    role = discord.utils.get(ctx.guild.roles, name="Senator") or discord.utils.get(ctx.guild.roles, name="Representative")
                    if role:
                        await member.remove_roles(role)

            # Notify admin
            admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
            await admin_channel.send(f"Legislator {legislator_name} no longer in API. Role removed from {user.mention}")

            # Remove from database
            cursor.execute("DELETE FROM verified_users WHERE discord_id = ?", (discord_id,))
            conn.commit()


            bot.run(TOKEN)
