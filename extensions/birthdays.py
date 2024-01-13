import discord
import aiosqlite

from discord.ext import commands
from discord.ui import View, Button

months = [
    {"name": "January", "value": 1},
    {"name": "February", "value": 2},
    {"name": "March", "value": 3},
    {"name": "April", "value": 4},
    {"name": "May", "value": 5},
    {"name": "June", "value": 6},
    {"name": "July", "value": 7},
    {"name": "August", "value": 8},
    {"name": "September", "value": 9},
    {"name": "October", "value": 10},
    {"name": "November", "value": 11},
    {"name": "December", "value": 12},
]


class BirthdayPaginationView(View):
    def __init__(self, embeds):
        super().__init__()
        self.embeds = embeds
        self.current_page = 0

    @discord.ui.button(
        label="Previous", style=discord.ButtonStyle.grey, custom_id="previous"
    )
    async def previous_button_callback(
        self, button: Button, interaction: discord.Interaction
    ):
        if self.current_page == 0:
            button.disabled = True

        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page]
            )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.grey, custom_id="next")
    async def next_button_callback(self, button: Button, interaction: discord):
        if self.current_page == len(self.embeds) - 1:
            button.disabled = True

        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page]
            )

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="close")
    async def close_button_callback(self, button, interaction: discord.Interaction):
        await interaction.response.edit_message(view=None)
        await interaction.message.delete()


class Birthdays(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"

    _birthdays = discord.commands.SlashCommandGroup(
        name="birthdays",
        description="Commands for birthdays",
    )

    async def months_autocomplete(self, ctx: discord.ApplicationContext):
        return [discord.OptionChoice(name=m["name"], value=m["value"]) for m in months]

    @_birthdays.command(name="set", description="Set your birthday")
    async def set_birthday(
        self,
        ctx: commands.Context,
        month: discord.Option(
            int,
            description="Month of your birthday",
            autocomplete=months_autocomplete,
        ),
        day: discord.Option(
            int,
            description="Day of your birthday",
        ),
    ):
        await ctx.defer()

        if day not in range(1, 32):
            return await ctx.respond(f"😅 {day} days in a month? Even my calculator is confused. Try a day from 1 to 31!"   ) # fmt: skip

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS birthdays (user_id INTEGER PRIMARY KEY, guild_id INTEGER, month INTEGER, day INTEGER)"
            )
            await db.commit()

            async with db.execute(
                "SELECT * FROM birthdays WHERE user_id = ? AND guild_id = ?",
                (ctx.author.id, ctx.guild.id),
            ) as cursor:
                if await cursor.fetchone():
                    await db.execute(
                        "UPDATE birthdays SET month = ?, day = ? WHERE user_id = ? AND guild_id = ?",
                        (month, day, ctx.author.id, ctx.guild.id),
                    )
                else:
                    await db.execute(
                        "INSERT INTO birthdays (user_id, guild_id, month, day) VALUES (?, ?, ?, ?)",
                        (ctx.author.id, ctx.guild.id, month, day),
                    )
                await db.commit()

        month_name = months[month - 1]["name"]
        await ctx.respond(f"🎉 Your birthday has been set to {month_name} {day}!")

    @_birthdays.command(name="view", description="View everyone's birthday")
    async def view_birthdays(self, ctx: commands.Context):
        await ctx.defer()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM birthdays WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                birthdays = await cursor.fetchall()

        if not birthdays:
            return await ctx.respond("😅 No one has set their birthday yet!")

        embeds = []

        for birthday in birthdays:
            user = ctx.guild.get_member(birthday[0])
            if not user:
                continue

            month_name = months[birthday[2] - 1]["name"]
            embed = discord.Embed(
                title=f"{user.nick or user.name}'s Birthday",
                description=f"{month_name} {birthday[3]}",
                color=discord.Color.embed_background(),
            )
            embed.set_thumbnail(url=user.avatar.url)
            embeds.append(embed)

        view = BirthdayPaginationView(embeds)

        await ctx.respond(embed=embeds[0], view=view)

    @_birthdays.command(name="get", description="Get someone's birthday")
    async def get_birthday(
        self,
        ctx: commands.Context,
        user: discord.Option(
            discord.Member,
            description="User to get birthday of",
        ),
    ):
        await ctx.defer()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM birthdays WHERE user_id = ? AND guild_id = ?",
                (user.id, ctx.guild.id),
            ) as cursor:
                birthday = await cursor.fetchone()

        if not birthday:
            return await ctx.respond(f"😅 {user.name} hasn't set their birthday yet!")

        month_name = months[birthday[2] - 1]["name"]
        await ctx.respond(f"🎉 {user.name}'s birthday is {month_name} {birthday[3]}!")


def setup(bot_: discord.Bot):
    bot_.add_cog(Birthdays(bot_))
