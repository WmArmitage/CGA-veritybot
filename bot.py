import discord
from discord.ext import commands
import sqlite3
import io
import os

# Replace with your actual values
#TOKEN = 'YOUR_BOT_TOKEN' - see line 16
ADMIN_ROLE_ID = 1242292827510276269
APPROVAL_CHANNEL_ID = 1242300716119494806
SENATOR_ROLE_ID = 1242296657933107221
REPRESENTATIVE_ROLE_ID = 1242296757954674758
CGA_STAFF_ROLE_ID = 1244067941662720061
PRESS_ROLE_ID = 1242989393049030727
GUILD_ID = 1242198415547433030
DATABASE_FILE = 'role_requests.db' #database file name

TOKEN = os.getenv("TOKEN")  # Read from Railway variables


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
conn = sqlite3.connect('role_requests.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS role_requests
                  (discord_id INTEGER PRIMARY KEY, username TEXT, role_id INTEGER, approved INTEGER DEFAULT 0)''')
conn.commit()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

async def handle_role_request(ctx, role_id, role_name):
    user_id = ctx.author.id
    username = ctx.author.name

    cursor.execute("SELECT * FROM role_requests WHERE discord_id = ? AND role_id = ?", (user_id, role_id))
    existing_request = cursor.fetchone()

    if existing_request:
        if existing_request[3] == 1:
            await ctx.send(f"You already have the {role_name} role.")
        else:
            await ctx.send(f"You have already requested the {role_name} role. Please wait for approval.")
        return

    cursor.execute("INSERT INTO role_requests (discord_id, username, role_id) VALUES (?, ?, ?)", (user_id, username, role_id))
    conn.commit()

    approval_channel = bot.get_channel(APPROVAL_CHANNEL_ID)
    if approval_channel:
        await approval_channel.send(f"User {ctx.author.mention} requests the {role_name} role.")
        await ctx.send(f"Your request for the {role_name} role has been submitted for approval.")
    else:
        await ctx.send("Role request submitted. Approval channel not found.")

    await send_pending_requests_embed(ctx.guild)

async def send_pending_requests_embed(guild):
    cursor.execute("SELECT discord_id, username, role_id FROM role_requests WHERE approved = 0")
    requests = cursor.fetchall()

    if not requests:
        return

    embed = discord.Embed(title="Pending Role Requests", color=0x00ff00)

    for user_id, username, role_id in requests:
        user = guild.get_member(user_id)
        role = guild.get_role(role_id)
        if user and role:
            embed.add_field(name=username, value=f"Requesting: {role.name}", inline=False)
            view = discord.ui.View()
            approve_button = discord.ui.Button(label="Approve", style=discord.ButtonStyle.success, custom_id=f"approve_{user_id}_{role_id}")
            decline_button = discord.ui.Button(label="Decline", style=discord.ButtonStyle.danger, custom_id=f"decline_{user_id}_{role_id}")
            view.add_item(approve_button)
            view.add_item(decline_button)
            approval_channel = bot.get_channel(APPROVAL_CHANNEL_ID)
            await approval_channel.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.data and interaction.data["custom_id"].startswith("approve_"):
        # ... (approve logic) ...
    elif interaction.data and interaction.data["custom_id"].startswith("decline_"):
        # ... (decline logic) ...

@bot.command()
async def viewdb(ctx):
    # ... (viewdb logic) ...

@bot.command()
async def senator(ctx):
    await handle_role_request(ctx, SENATOR_ROLE_ID, "Senator")

@bot.command()
async def representative(ctx):
    await handle_role_request(ctx, REPRESENTATIVE_ROLE_ID, "Representative")

@bot.command()
async def cgastaff(ctx):
    await handle_role_request(ctx, CGA_STAFF_ROLE_ID, "CGA Staff")

@bot.command()
async def pressmedia(ctx):
    await handle_role_request(ctx, PRESS_ROLE_ID, "Press Media")

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        removed_roles = [role for role in before.roles if role not in after.roles]
        for role in removed_roles:
            cursor.execute("DELETE FROM role_requests WHERE discord_id = ? AND role_id = ? AND approved = 1", (after.id, role.id))
            conn.commit()
            print(f"Removed role {role.name} for user {after.name} from database.")

bot.run(TOKEN)
