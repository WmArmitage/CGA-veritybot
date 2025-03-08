import discord
from discord.ext import commands
from discord import app_commands
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
"""
conn = sqlite3.connect(DATABASE_FILE)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS role_requests
                  (discord_id INTEGER PRIMARY KEY, username TEXT, role_id INTEGER, approved INTEGER DEFAULT 0, request_reason TEXT, decline_reason TEXT)''')
cursor.execute("CREATE INDEX IF NOT EXISTS idx_approved ON role_requests (approved)") # database index
conn.commit()
"""
conn = sqlite3.connect(DATABASE_FILE)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS role_requests (
                  discord_id INTEGER,
                  username TEXT,
                  role_id INTEGER,
                  approved INTEGER DEFAULT 0,
                  request_reason TEXT,
                  decline_reason TEXT,
                  PRIMARY KEY (discord_id, role_id))''')
cursor.execute("CREATE INDEX IF NOT EXISTS idx_approved ON role_requests (approved)")
conn.commit()





#bot code begins here

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)



class RoleRequestModal(discord.ui.Modal):
    def __init__(self, role_id, role_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role_id = role_id
        self.role_name = role_name
        self.add_item(discord.ui.TextInput(label="Why do you want this role?", style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Retrieve the reason from the modal's text input
            reason = self.children[0].value
            user_id = interaction.user.id
            username = interaction.user.name

            # Attempt to insert the request into the database
            cursor.execute("INSERT INTO role_requests (discord_id, username, role_id, request_reason) VALUES (?, ?, ?, ?)",
                           (user_id, username, self.role_id, reason))
            conn.commit()

            # Send a confirmation response to the user
            await interaction.response.send_message(f"Your request for {self.role_name} has been submitted.", ephemeral=True)

            # Update pending requests embed and log the request
            await send_pending_requests_embed(interaction.guild)
            await log_audit(interaction.guild, interaction.user, f"Requested role: {self.role_name}, Reason: {reason}")
        except sqlite3.Error as db_error:
            # Handle database-related errors
            print(f"Database error: {db_error}")
            await interaction.response.send_message("There was an issue saving your request. Please try again later.", ephemeral=True)
        except Exception as e:
            # Catch any other unexpected errors
            print(f"Unexpected error: {e}")
            await interaction.response.send_message("An unexpected error occurred. Please try again.", ephemeral=True)




async def send_pending_requests_embed(guild):
    try:
        cursor.execute("SELECT discord_id, username, role_id, request_reason FROM role_requests WHERE approved = 0")
        requests = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return

    if not requests:
        approval_channel = bot.get_channel(APPROVAL_CHANNEL_ID)
        if approval_channel:
            await approval_channel.send("No pending role requests at the moment.")
        return

    approval_channel = bot.get_channel(APPROVAL_CHANNEL_ID)
    if not approval_channel:
        print(f"Approval channel with ID {APPROVAL_CHANNEL_ID} not found.")
        return

    embed = discord.Embed(title="Pending Role Requests", color=0x00ff00)

    view = discord.ui.View()  # Create a view for the buttons

    for user_id, username, role_id, request_reason in requests:
        role = guild.get_role(role_id)
        if not role:
            print(f"Role with ID {role_id} not found in guild {guild.name}.")
            continue

        embed.add_field(name=username, value=f"**Role:** {role.name}\n**Reason:** {request_reason}", inline=False)

        # Create buttons for each request
        approve_button = discord.ui.Button(label="Approve", style=discord.ButtonStyle.success, custom_id=f"approve_{user_id}_{role_id}")
        decline_button = discord.ui.Button(label="Decline", style=discord.ButtonStyle.danger, custom_id=f"decline_{user_id}_{role_id}")
        view.add_item(approve_button)
        view.add_item(decline_button)

    await approval_channel.send(embed=embed, view=view)

      
 # Create buttons for each request
        approve_button = discord.ui.Button(label="Approve", style=discord.ButtonStyle.success, custom_id=f"approve_{user_id}_{role_id}")
        decline_button = discord.ui.Button(label="Decline", style=discord.ButtonStyle.danger, custom_id=f"decline_{user_id}_{role_id}")
        view.add_item(approve_button)
        view.add_item(decline_button)

    await approval_channel.send(embed=embed)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    custom_id = interaction.data.get("custom_id", "")

    if not custom_id:
        await interaction.response.send_message("Interaction has no valid custom ID.", ephemeral=True)
        return

    if custom_id.startswith("approve_") or custom_id.startswith("decline_"):
        parts = custom_id.split("_")
        if len(parts) != 3:
            await interaction.response.send_message("Invalid interaction format.", ephemeral=True)
            return

        action, user_id, role_id = parts
        user_id = int(user_id)
        role_id = int(role_id)

        admin_role = discord.utils.get(interaction.guild.roles, id=ADMIN_ROLE_ID)
        if admin_role not in interaction.user.roles:
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return

        guild = interaction.guild
        member = guild.get_member(user_id)
        role = guild.get_role(role_id)

        if not member:
            print(f"Member with ID {user_id} not found in guild {guild.name}.")
            await interaction.response.send_message("User not found.", ephemeral=True)
            return
        if not role:
            print(f"Role with ID {role_id} not found in guild {guild.name}.")
            await interaction.response.send_message("Role not found.", ephemeral=True)
            return

        cursor.execute("SELECT approved FROM role_requests WHERE discord_id = ? AND role_id = ?", (user_id, role_id))
        result = cursor.fetchone()

        if action == "approve":
            if result and result[0] == 1:
                await interaction.response.send_message("This request has already been approved.", ephemeral=True)
                return
            elif not result:
                await interaction.response.send_message("No matching request found.", ephemeral=True)
                return
            try:
                await member.add_roles(role)
                cursor.execute("UPDATE role_requests SET approved = 1 WHERE discord_id = ? AND role_id = ?", (user_id, role_id))
                conn.commit()
                await interaction.response.send_message(f"Approved {member.name} for {role.name}.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("No permission to assign role.", ephemeral=True)
            except Exception as e:
                print(f"Unexpected error during role approval: {e}")
                await interaction.response.send_message("An unexpected error occurred. Please contact an admin.", ephemeral=True)

        elif action == "decline":
            await interaction.response.defer(ephemeral=True)
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
            cursor.execute(
                "UPDATE role_requests SET decline_reason = ? WHERE discord_id = ? AND role_id = ?",
                (reason, self.user_id, self.role_id)
            )
            cursor.execute(
                "DELETE FROM role_requests WHERE discord_id = ? AND role_id = ? AND approved = 0",
                (self.user_id, self.role_id)
            )
            conn.commit()

            # Defer and send a follow-up response
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("Request declined successfully.", ephemeral=True)

            # Update embed and log audit
            await send_pending_requests_embed(interaction.guild)
            await log_audit(
                interaction.guild, interaction.user,
                f"Declined request from user ID: {self.user_id}, Role ID: {self.role_id}, Reason: {reason}."
            )
        except sqlite3.Error as e:
            await interaction.response.send_message(f"Database error: {e}", ephemeral=True)


@bot.command() 
async def viewdb(interaction: discord.Interaction):
    admin_role = discord.utils.get(interaction.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role not in interaction.user.roles: 
        await interaction.response.send_message("You do not have permission to view the database.")
        return
    try:
        with open(DATABASE_FILE, 'rb') as f:
            await interaction.response.send_message(file=discord.File(f, 'role_requests.db'))
    except FileNotFoundError:
        await interaction.response.send_message("Database file not found.")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")

#define roles

@bot.tree.command(name="pressmedia", description="Request the Press Media role")
async def pressmedia(interaction: discord.Interaction):
    await handle_role_request(interaction, PRESS_ROLE_ID, "Press Media")

@bot.tree.command(name="senator", description="Request the Senator role")
async def senator(interaction: discord.Interaction):
    await handle_role_request(interaction, SENATOR_ROLE_ID, "Senator")

@bot.tree.command(name="representative", description="Request the Representative role")
async def representative(interaction: discord.Interaction):
    await handle_role_request(interaction, REPRESENTATIVE_ROLE_ID, "Representative")

@bot.tree.command(name="cgastaff", description="Request the CGA Staff role")
async def cgastaff(interaction: discord.Interaction):
    await handle_role_request(interaction, CGA_STAFF_ROLE_ID, "CGA Staff")

async def handle_role_request(interaction: discord.Interaction, role_id, role_name):
    await interaction.response.send_modal(RoleRequestModal(role_id, role_name, title=f"Request {role_name}"))



                 
bot.run(TOKEN)

