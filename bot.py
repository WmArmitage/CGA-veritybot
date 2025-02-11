import discord
from discord.ext import commands
import sqlite3
import asyncio

TOKEN = "YOUR_DISCORD_BOT_TOKEN"
GUILD_ID = YOUR_GUILD_ID  # Replace with your Discord server ID

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Database Setup
conn = sqlite3.connect("verification.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS verification (
                user_id INTEGER PRIMARY KEY,
                email TEXT,
                role_requested TEXT,
                attempts INTEGER DEFAULT 0,
                verified INTEGER DEFAULT 0
            )''')
conn.commit()

# Role Limits
ROLE_LIMITS = {
    "Senator": 36,
    "Representative": 151
}

# Function to get role by name
def get_role(guild, role_name):
    return discord.utils.get(guild.roles, name=role_name)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def verify(ctx, email: str, role: str):
    """Command to verify users with email and assign roles."""
    if role not in ["Senator", "Representative", "CGA Staff", "Press/Media"]:
        await ctx.send("Invalid role selection.")
        return
    
    if "@cga.ct.gov" not in email and role in ["Senator", "Representative", "CGA Staff"]:
        await ctx.send("Invalid email domain. Only @cga.ct.gov emails are allowed for this role.")
        return
    
    user_id = ctx.author.id
    c.execute("SELECT attempts, verified FROM verification WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    
    if row:
        attempts, verified = row
        if verified:
            await ctx.send("You are already verified.")
            return
        if attempts >= 3:
            await ctx.send("You have reached the maximum number of attempts. Please contact an admin.")
            return
    else:
        c.execute("INSERT INTO verification (user_id, email, role_requested, attempts) VALUES (?, ?, ?, 1)",
                  (user_id, email, role))
    conn.commit()
    
    # Simulate Email Verification Process (Future Expansion for OTP System)
    await asyncio.sleep(5)  # Simulate delay for email verification
    
    guild = bot.get_guild(GUILD_ID)
    role_obj = get_role(guild, role)
    if role in ROLE_LIMITS and len(role_obj.members) >= ROLE_LIMITS[role]:
        await ctx.send(f"Role {role} is at maximum capacity ({ROLE_LIMITS[role]}). Contact admin.")
        return
    
    await ctx.author.add_roles(role_obj)
    c.execute("UPDATE verification SET verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    await ctx.send(f"{ctx.author.mention}, you have been verified and assigned the role: {role}.")

@bot.command()
@commands.has_role("Administrator")
async def reset_verification(ctx, member: discord.Member):
    """Admin command to reset a user's verification attempts."""
    c.execute("UPDATE verification SET attempts = 0, verified = 0 WHERE user_id = ?", (member.id,))
    conn.commit()
    await ctx.send(f"Verification reset for {member.mention}.")

@bot.command()
@commands.has_role("Administrator")
async def recent_verifications(ctx):
    """Admin command to check the last 5 verification attempts."""
    c.execute("SELECT user_id, email, role_requested, attempts, verified FROM verification ORDER BY user_id DESC LIMIT 5")
    rows = c.fetchall()
    response = "Last 5 verification attempts:\n"
    for row in rows:
        response += f"User ID: {row[0]}, Email: {row[1]}, Role: {row[2]}, Attempts: {row[3]}, Verified: {row[4]}\n"
    await ctx.send(f"```{response}```")

bot.run(TOKEN)
#comment to try and fix /bin/bash: line 1: ./bot.py: Permission denied error
