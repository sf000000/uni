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
        name="coinflip",
        description="Flip a coin.",
    )
    async def coinflip(
        self,
        ctx: discord.ApplicationContext,
        amount: discord.Option(
            int, description="The amount of money to gamble.", required=True
        ),
        coin_choice: discord.Option(
            str,
            description="The side of the coin to bet on.",
            required=True,
            choices=["heads", "tails"],
        ),
    ):
        if amount <= 0:
            return await ctx.respond(
                "You can't gamble a negative amount.", ephemeral=True
            )

        balance = await self.get_balance(ctx.user.id, ctx.guild.id)
        if balance is None:
            return await ctx.respond(
                "You don't have a balance yet. Use `/bank collect` to get started.",
                ephemeral=True,
            )

        if balance[0] < amount:
            return await ctx.respond(
                "You don't have enough money to gamble that amount.", ephemeral=True
            )

        coin = random.choice(["heads", "tails"])

        if coin == coin_choice:
            await self.update_balance(ctx.user.id, ctx.guild.id, amount, True)
            embed = discord.Embed(
                title="Coinflip",
                description=f"You've won **{amount}** {config['ECONOMY']['CURRENCY_NAME']}!",
                color=config["COLORS"]["SUCCESS"],
            )
        else:
            await self.update_balance(ctx.user.id, ctx.guild.id, amount, False)
            embed = discord.Embed(
                title="Coinflip",
                description=f"You've lost **{amount}** {config['ECONOMY']['CURRENCY_NAME']}!",
                color=config["COLORS"]["ERROR"],
            )

        embed.add_field(name="Coin", value=coin, inline=False)
        await ctx.respond(embed=embed)


def setup(bot_: discord.Bot):
    bot_.add_cog(Economy(bot_))
