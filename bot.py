import discord
from discord.ext import commands
import sqlite3
import io
import os
import datetime

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
AUDIT_LOG_CHANNEL_ID = 1347258435452014703

TOKEN = os.getenv("TOKEN")  # Read from Railway variables


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)



# Database setup
conn = sqlite3.connect(DATABASE_FILE)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS role_requests
                  (discord_id INTEGER PRIMARY KEY, username TEXT, role_id INTEGER, approved INTEGER DEFAULT 0, request_reason TEXT, decline_reason TEXT)''')
cursor.execute("CREATE INDEX IF NOT EXISTS idx_approved ON role_requests (approved)") #database index
conn.commit()

# new code start

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

class RoleRequestModal(discord.ui.Modal):
    def __init__(self, role_id, role_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role_id = role_id
        self.role_name = role_name

        self.add_item(discord.ui.TextInput(label="Why do you want this role?", style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.children[0].value
        user_id = interaction.user.id
        username = interaction.user.name
        try:
            cursor.execute("INSERT INTO role_requests (discord_id, username, role_id, request_reason) VALUES (?, ?, ?, ?)", (user_id, username, self.role_id, reason))
            conn.commit()
            await interaction.response.send_message(f"Your request for {self.role_name} has been submitted.", ephemeral=True)
            await send_pending_requests_embed(interaction.guild)
            await log_audit(interaction.guild, interaction.user, f"Requested role: {self.role_name}, Reason: {reason}")
        except sqlite3.Error as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)      
      
# new code end
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
  
#commenting out
#async def handle_role_request(ctx, role_id, role_name):
    #user_id = ctx.author.id
    #username = ctx.author.name

#new code start 
async def handle_role_request(ctx, role_id, role_name):
    await ctx.interaction.response.send_modal(RoleRequestModal(role_id, role_name, title=f"Request {role_name}"))
#new code end
  
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
        custom_id = interaction.data["custom_id"]
        _, user_id, role_id = custom_id.split("_")
        user_id = int(user_id)
        role_id = int(role_id)

        admin_role = discord.utils.get(interaction.guild.roles, id=ADMIN_ROLE_ID)
        if admin_role not in interaction.user.roles:
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return

        cursor.execute("SELECT * FROM role_requests WHERE discord_id = ? AND role_id = ? AND approved = 0", (user_id, role_id))
        request = cursor.fetchone()

        if not request:
            await interaction.response.send_message("Request not found.", ephemeral=True)
            return

        guild = bot.get_guild(interaction.guild_id)
        member = guild.get_member(user_id)
        role = guild.get_role(role_id)

        if member and role:
            try:
                await member.add_roles(role)
                cursor.execute("UPDATE role_requests SET approved = 1 WHERE discord_id = ? AND role_id = ?", (user_id, role_id))
                conn.commit()
                await interaction.response.send_message(f"Approved {member.name}'s request for {role.name}.", ephemeral=True)
                await send_pending_requests_embed(interaction.guild)
            except discord.Forbidden:
                await interaction.response.send_message("No permission to assign role.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("User or role not found.", ephemeral=True)
    elif interaction.data and interaction.data["custom_id"].startswith("decline_"):
        custom_id = interaction.data["custom_id"]
        _, user_id, role_id = custom_id.split("_")
        user_id = int(user_id)
        role_id = int(role_id)

        admin_role = discord.utils.get(interaction.guild.roles, id=ADMIN_ROLE_ID)
        if admin_role not in interaction.user.roles:
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return

        cursor.execute("DELETE FROM role_requests WHERE discord_id = ? AND role_id = ? AND approved = 0", (user_id, role_id))
        conn.commit()
        await interaction.response.send_message("Request declined.", ephemeral=True)
        await send_pending_requests_embed(interaction.guild)

@bot.command()
async def viewdb(ctx):
    admin_role = discord.utils.get(ctx.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role not in ctx.author.roles:
        await ctx.send("You do not have permission to view the database.")
        return

    try:
        with open(DATABASE_FILE, 'rb') as f:
            await ctx.send(file=discord.File(f, 'role_requests.db'))
    except FileNotFoundError:
        await ctx.send("Database file not found.")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

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
