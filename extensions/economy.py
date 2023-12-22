import discord
import aiosqlite
import yaml
import random

from discord.ext import commands


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Economy(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        command_name = ctx.command.name

        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM disabled_commands WHERE command = ?", (command_name,)
            )
            if await cur.fetchone():
                embed = discord.Embed(
                    title="Command Disabled",
                    description=f"The command `{command_name}` is currently disabled in this guild.",
                    color=discord.Color.red(),
                )
                embed.set_footer(text="This message will be deleted in 10 seconds.")
                embed.set_author(
                    name=self.bot.user.display_name, icon_url=self.bot.user.avatar.url
                )
                await ctx.respond(embed=embed, ephemeral=True, delete_after=10)
                raise commands.CommandInvokeError(
                    f"Command `{command_name}` is disabled."
                )

    async def member_autocomplete(self, ctx: discord.ApplicationContext, string: str):
        members = ctx.guild.members
        return [
            member
            for member in members
            if string.lower() in member.display_name.lower()
        ]

    # CREATE TABLE IF NOT EXISTS economy ( user_id INTEGER PRIMARY KEY, guild_id INTEGER, balance REAL DEFAULT 0, daily_cooldown INTEGER DEFAULT 0, last_daily INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0 );
    async def get_balance(self, user_id: int, guild_id: int):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT balance FROM economy WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            )
            return await cur.fetchone()

    async def update_balance(
        self, user_id: int, guild_id: int, amount: int, add: bool = True
    ):
        async with self.conn.cursor() as cur:
            if add:
                await cur.execute(
                    "UPDATE economy SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
                    (amount, user_id, guild_id),
                )
            else:
                await cur.execute(
                    "UPDATE economy SET balance = balance - ? WHERE user_id = ? AND guild_id = ?",
                    (amount, user_id, guild_id),
                )
            await self.conn.commit()

    def calculate_reward(self, chosen_slots, bet_amount, mention, currency_name):
        if chosen_slots[0] == chosen_slots[1] == chosen_slots[2]:
            reward = bet_amount * 5
            return (
                reward,
                f"{mention} Jackpot! You've won **{reward}** {currency_name}!",
            )
        elif len(set(chosen_slots)) < 3:
            reward = bet_amount * 2
            return reward, f"{mention} Nice! You've won **{reward}** {currency_name}!"
        return (
            -bet_amount,
            f"{mention} Better luck next time! You've lost **{bet_amount}** {currency_name}!",
        )

    _bank = discord.commands.SlashCommandGroup(
        name="bank",
        description="Manage your bank.",
    )

    @_bank.command(
        name="balance",
        description="Check your balance.",
    )
    async def balance(self, ctx: discord.ApplicationContext):
        balance = await self.get_balance(ctx.user.id, ctx.guild.id)
        if balance is None:
            await ctx.respond(
                "You don't have a balance yet. Use `/bank collect` to get started.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Balance",
            description=f"Your balance is **{balance[0]}** {config['ECONOMY']['CURRENCY_NAME']}.",
            color=config["COLORS"]["SUCCESS"],
        )
        await ctx.respond(embed=embed)

    @_bank.command(
        name="collect",
        description="Collect your daily coins.",
    )
    async def collect(self, ctx: discord.ApplicationContext):
        balance = await self.get_balance(ctx.user.id, ctx.guild.id)
        if balance is None:
            await self.conn.execute(
                "INSERT INTO economy (user_id, guild_id) VALUES (?, ?)",
                (ctx.user.id, ctx.guild.id),
            )
            await self.conn.commit()
            balance = await self.get_balance(ctx.user.id, ctx.guild.id)

        if balance[0] != 0:
            await ctx.respond(
                "You've already claimed your daily coins today.", ephemeral=True
            )
            return

        await self.conn.execute(
            "UPDATE economy SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
            (config["ECONOMY"]["DAILY_AMOUNT"], ctx.user.id, ctx.guild.id),
        )
        await self.conn.commit()

        embed = discord.Embed(
            title="Daily Coins",
            description=f"You've claimed your daily coins of **{config['ECONOMY']['DAILY_AMOUNT']}** {config['ECONOMY']['CURRENCY_NAME']}.",
            color=config["COLORS"]["SUCCESS"],
        )
        await ctx.respond(embed=embed)

    @_bank.command(
        name="add",
        description="Add money to a user's balance.",
    )
    @commands.is_owner()
    async def add(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(
            discord.Member,
            description="The user to add money to.",
            required=True,
            autocomplete=member_autocomplete,
        ),
        amount: discord.Option(
            int, description="The amount of money to add.", required=True
        ),
    ):
        if amount <= 0:
            return await ctx.respond("You can't add a negative amount.", ephemeral=True)

        await self.update_balance(user.id, ctx.guild.id, amount, True)

        embed = discord.Embed(
            title="Add",
            description=f"You've added **{amount}** {config['ECONOMY']['CURRENCY_NAME']} to {user.mention}'s balance.",
            color=config["COLORS"]["SUCCESS"],
        )
        await ctx.respond(embed=embed)

    @_bank.command(
        name="transfer",
        description="Transfer money to another user.",
    )
    async def transfer(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(
            discord.Member,
            description="The user to transfer money to.",
            required=True,
            autocomplete=member_autocomplete,
        ),
        amount: discord.Option(
            int, description="The amount of money to transfer.", required=True
        ),
    ):
        if user == ctx.user:
            return await ctx.respond(
                "You can't transfer money to yourself.", ephemeral=True
            )

        if amount <= 0:
            return await ctx.respond(
                "You can't transfer a negative amount.", ephemeral=True
            )

        balance = await self.get_balance(ctx.user.id, ctx.guild.id)
        if balance is None:
            return await ctx.respond(
                "You don't have a balance yet. Use `/bank collect` to get started.",
                ephemeral=True,
            )

        if balance[0] < amount:
            return await ctx.respond(
                "You don't have enough money to transfer that amount.", ephemeral=True
            )

        user_balance = await self.get_balance(user.id, ctx.guild.id)
        if user_balance is None:
            await self.conn.execute(
                "INSERT INTO economy (user_id, guild_id) VALUES (?, ?)",
                (user.id, ctx.guild.id),
            )
            await self.conn.commit()
            user_balance = await self.get_balance(user.id, ctx.guild.id)

        await self.update_balance(ctx.user.id, ctx.guild.id, amount, False)
        await self.update_balance(user.id, ctx.guild.id, amount, True)

        embed = discord.Embed(
            title="Transfer",
            description=f"You've transferred **{amount}** {config['ECONOMY']['CURRENCY_NAME']} to {user.mention}.",
            color=config["COLORS"]["SUCCESS"],
        )
        await ctx.respond(embed=embed)

    _gamble = discord.commands.SlashCommandGroup(
        name="gamble",
        description="Gamble your money away.",
    )

    @_gamble.command(
        name="slots",
        description="Play the slots.",
    )
    async def slots(
        self,
        ctx: discord.ApplicationContext,
        amount: discord.Option(
            int, description="The amount of money to gamble.", required=True
        ),
    ):
        if amount <= 0:
            return await ctx.respond(
                "You can't gamble a negative or zero amount.", ephemeral=True
            )

        balance = await self.get_balance(ctx.user.id, ctx.guild.id)
        if not balance or balance[0] < amount:
            message = (
                "You don't have a balance yet. Use `/bank collect` to get started."
                if not balance
                else "You don't have enough money to gamble that amount."
            )
            return await ctx.respond(message, ephemeral=True)

        slots = ["💝", "🎉", "💎", "💵", "💰", "🚀", "🍿"]
        chosen_slots = random.choices(slots, k=3)
        slots_display = " | ".join(chosen_slots)

        reward, content = self.calculate_reward(
            chosen_slots, amount, ctx.author.mention, config["ECONOMY"]["CURRENCY_NAME"]
        )
        await self.update_balance(ctx.user.id, ctx.guild.id, reward, reward > 0)

        embed = discord.Embed(
            description=f"```\n| {slots_display} |\n```",
            color=config["COLORS"]["SUCCESS"]
            if reward > 0
            else config["COLORS"]["ERROR"],
        )
        await ctx.respond(
            content=content,
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )


def setup(bot_: discord.Bot):
    bot_.add_cog(Economy(bot_))
