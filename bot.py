import discord
from discord.ext import commands
import sqlite3
import io
import os
import datetime

# Replace with your actual values

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
cursor.execute("CREATE INDEX IF NOT EXISTS idx_approved ON role_requests (approved)") # database index
conn.commit()



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


async def handle_role_request(ctx, role_id, role_name):
    await ctx.interaction.response.send_modal(RoleRequestModal(role_id, role_name, title=f"Request {role_name}"))

async def send_pending_requests_embed(guild):
    cursor.execute("SELECT discord_id, username, role_id, request_reason FROM role_requests WHERE approved = 0")
    requests = cursor.fetchall()

    if not requests:
        return

    embed = discord.Embed(title="Pending Role Requests", color=0x00ff00)

    for user_id, username, role_id, request_reason in requests:
        user = guild.get_member(user_id)
        role = guild.get_role(role_id)
        if user and role:
            embed.add_field(name=username, value=f"Requesting: {role.name}\nReason: {request_reason}", inline=False)
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
                await log_audit(interaction.guild, interaction.user, f"Approved {member.name}'s request for {role.name}.")
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
        await interaction.response.send_modal(DeclineReasonModal(user_id, role_id))

class DeclineReasonModal(discord.ui.Modal):
    def __init__(self, user_id, role_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = user_id
        self.role_id = role_id
        self.add_item(discord.ui.TextInput(label="Reason for Decline", style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.children[0].value
        try:
            cursor.execute(f"UPDATE role_requests SET decline_reason = '{reason}' WHERE discord_id = {self.user_id} AND role_id = {self.role_id}")
            cursor.execute(f"DELETE FROM role_requests WHERE discord_id = {self.user_id} AND role_id = {self.role_id} AND approved = 0")
            conn.commit()
            await interaction.response.send_message("Request declined.", ephemeral=True)
            await send_pending_requests_embed(interaction.guild)
            await log_audit(interaction.guild, interaction.user, f"Declined request from user ID: {self.user_id}, Role ID: {self.role_id}, Reason: {reason}.")
        except sqlite3.Error as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)

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

#define roles

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


#this logic handles the code not checking to see if the role has been removed drom Discord, but database did not reflect that so it assumed role was still apllied
@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        removed_roles = [role for role in before.roles if role not in after.roles]
        for role in removed_roles:
            cursor.execute("DELETE FROM role_requests WHERE discord_id = ? AND role_id = ? AND approved = 1", (after.id, role.id))
            conn.commit()
            print(f"Removed role {role.name} for user {after.name} from database.")

async def log_audit(guild, user, action):
    channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title="Audit Log", description=action, timestamp=datetime.datetime.now())
        embed.set_author(name=user.name, icon_url=user.avatar.url if user.avatar else "")
        await channel.send(embed=embed)


                 
bot.run(TOKEN)

