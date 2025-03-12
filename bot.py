import discord
from discord.ext import commands
import sqlite3
import os

# Replace with your actual values

ADMIN_ROLE_ID = 1242292827510276269
APPROVAL_CHANNEL_ID = 1242300716119494806
SENATOR_ROLE_ID = 1242296657933107221
REPRESENTATIVE_ROLE_ID = 1242296757954674758
CGA_STAFF_ROLE_ID = 1244067941662720061
PRESS_ROLE_ID = 1244067941662720061
GUILD_ID = 1242198415547433030
DATABASE_FILE = 'role_requests.db' #database file name
AUDIT_LOG_CHANNEL_ID = 1347258435452014703

# Define roles
ROLE_IDS = {
    "Senator": 1242296657933107221,
    "Representative": 1242296757954674758,
    "CGA Staff": 1244067941662720061,
    "Press Media": 1244067941662720061
}



TOKEN = os.getenv("TOKEN")  # Read from Railway variables




# Database setup
conn = sqlite3.connect("verification.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS role_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                role_name TEXT,
                status TEXT)''')
conn.commit()



#bot code begins here

bot = commands.Bot(command_prefix="/", intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.tree.sync()

async def request_role(interaction: discord.Interaction, role_name: str):
    user_id = interaction.user.id
    c.execute("INSERT OR REPLACE INTO role_requests (user_id, role_name, status) VALUES (?, ?, 'pending')", (user_id, role_name))
    conn.commit()
    await interaction.response.send_message(f"Your request for the {role_name} role has been submitted.", ephemeral=True)

@bot.tree.command(name="requestrole", description="Request a role (Senator, Representative, CGA Staff, Press Media)")
async def requestrole(interaction: discord.Interaction, role: str):
    if role in ROLE_IDS:
        await request_role(interaction, role)
    else:
        await interaction.response.send_message("Invalid role name. Please select from: Senator, Representative, CGA Staff, Press Media.", ephemeral=True)

@bot.tree.command(name="approverole", description="Approve a role request (Admin only)")
@commands.has_permissions(administrator=True)
async def approverole(interaction: discord.Interaction, user: discord.User):
    c.execute("SELECT role_name FROM role_requests WHERE user_id = ? AND status = 'pending'", (user.id,))
    role_row = c.fetchone()
    if role_row:
        role_name = role_row[0]
        role = discord.utils.get(interaction.guild.roles, id=ROLE_IDS[role_name])
        if role:
            await user.add_roles(role)
            c.execute("UPDATE role_requests SET status = 'approved' WHERE user_id = ?", (user.id,))
            conn.commit()
            await interaction.response.send_message(f"Approved {role_name} role for {user.mention}.")
        else:
            await interaction.response.send_message("Role not found.")
    else:
        await interaction.response.send_message("No pending role request for this user.")

@bot.tree.command(name="denyrole", description="Deny a role request (Admin only)")
@commands.has_permissions(administrator=True)
async def denyrole(interaction: discord.Interaction, user: discord.User):
    c.execute("SELECT role_name FROM role_requests WHERE user_id = ? AND status = 'pending'", (user.id,))
    role_row = c.fetchone()
    if role_row:
        c.execute("UPDATE role_requests SET status = 'denied' WHERE user_id = ?", (user.id,))
        conn.commit()
        await interaction.response.send_message(f"Denied {role_row[0]} role request for {user.mention}.")
    else:
        await interaction.response.send_message("No pending role request for this user.")

bot.run("YOUR_BOT_TOKEN")

