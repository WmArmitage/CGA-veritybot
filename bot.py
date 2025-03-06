import discord
from discord.ext import commands
import sqlite3

# Replace with your actual values
#TOKEN = 'YOUR_BOT_TOKEN' - see line 16
ADMIN_ROLE_ID = 1242292827510276269
APPROVAL_CHANNEL_ID = 1267856155565363383
SENATOR_ROLE_ID = 1242296657933107221
REPRESENTATIVE_ROLE_ID = 1242296757954674758
CGA_STAFF_ROLE_ID = 1244067941662720061
PRESS_ROLE_ID = 1242989393049030727
GUILD_ID = 1242198415547433030

import os
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
    username = ctx.author.name  # Capture username

    # Check if the user already has the role or has requested it.
    cursor.execute("SELECT * FROM role_requests WHERE discord_id = ? AND role_id = ?", (user_id, role_id))
    existing_request = cursor.fetchone()

    if existing_request:
        if existing_request[3] == 1:
            await ctx.send(f"You already have the {role_name} role.")
        else:
            await ctx.send(f"You have already requested the {role_name} role. Please wait for approval.")
        return

    # Store the request in the database.
    cursor.execute("INSERT INTO role_requests (discord_id, username, role_id) VALUES (?, ?, ?)", (user_id, username, role_id))
    conn.commit()

    # Send a message to the approval channel.
    approval_channel = bot.get_channel(APPROVAL_CHANNEL_ID)
    if approval_channel:
        await approval_channel.send(f"User {ctx.author.mention} requests the {role_name} role. Use `!approve {ctx.author.id} {role_id}` to approve.")
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
            view.add_item(approve_button)
            approval_channel = bot.get_channel(APPROVAL_CHANNEL_ID)
            await approval_channel.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.data and interaction.data["custom_id"].startswith("approve_"):
        custom_id = interaction.data["custom_id"]
        _, user_id, role_id = custom_id.split("_")
        user_id = int(user_id)
        role_id = int(role_id)

        # ... (rest of your interaction logic) ...

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

bot.run(TOKEN)
