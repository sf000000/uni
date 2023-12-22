import discord
import aiosqlite
import yaml
import aiohttp
import asyncio

from discord.ext import commands


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class TriviaGame:
    def __init__(self, players, questions):
        self.players = players
        self.questions = questions
        self.current_question_index = -1
        self.scores = {player: 0 for player in players}


class AcceptChallengeView(discord.ui.View):
    def __init__(self, cog, challenger, opponent, question, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cog = cog
        self.challenger = challenger
        self.opponent = opponent
        self.question = question

    @discord.ui.button(label="Accept Challenge", style=discord.ButtonStyle.green)
    async def accept(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id == self.opponent.id:
            embed = self.cog.create_trivia_embed(self.question)
            await interaction.message.edit(content=None, embed=embed, view=None)
        else:
            await interaction.response.send_message(
                "Only the challenged opponent can accept the game!", ephemeral=True
            )


class Trivia(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())
        self.base_url = "https://opentdb.com/api.php"

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

    async def fetch_trivia_questions(self, category=None, difficulty=None):
        params = {
            "amount": 1,
        }
        if category:
            params["category"] = category
        if difficulty:
            params["difficulty"] = difficulty

        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("results", [])
                else:
                    print(f"Failed to fetch trivia questions: {response.status}")
                    return []

    def create_trivia_embed(self, trivia_question):
        embed = discord.Embed(title="Trivia Time!", color=discord.Color.blue())
        embed.add_field(
            name=f"Category: {trivia_question['category']}",
            value=f"Difficulty: {trivia_question['difficulty'].title()}",
            inline=False,
        )
        embed.add_field(
            name="Question",
            value=trivia_question["question"]
            .replace("&quot;", "**")
            .replace("&#039", "'"),
            inline=False,
        )

        if trivia_question["type"] == "multiple":
            choices = [trivia_question["correct_answer"]] + trivia_question[
                "incorrect_answers"
            ]
            choices_text = "\n".join(
                f"{chr(65+i)}. {choice}" for i, choice in enumerate(choices)
            )
            embed.add_field(name="Choices", value=choices_text)

        elif trivia_question["type"] == "boolean":
            embed.add_field(name="Choices", value="True or False (t, f)")

        return embed

    async def update_winner_score(self, winner_id, category):
        async with self.conn.execute(
            "SELECT wins FROM trivia_winners WHERE user_id = ? AND category = ?",
            (winner_id, category),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                current_wins = row[0]
                await self.conn.execute(
                    "UPDATE trivia_winners SET wins = ? WHERE user_id = ? AND category = ?",
                    (current_wins + 1, winner_id, category),
                )
            else:
                await self.conn.execute(
                    "INSERT INTO trivia_winners (user_id, category, wins) VALUES (?, ?, 1)",
                    (winner_id, category),
                )

            await self.conn.commit()

    _trivia = discord.commands.SlashCommandGroup(
        name="trivia",
        description="Trivia commands.",
    )

    @_trivia.command(
        name="challenge",
        description="Challenge someone to a game of trivia.",
    )
    async def _challenge(
        self,
        ctx: discord.ApplicationContext,
        opponent: discord.Option(
            discord.Member, description="The opponent to play against."
        ),
    ):
        if opponent == ctx.author:
            return await ctx.respond("You can't play against yourself!", ephemeral=True)

        if opponent.bot:
            return await ctx.respond("Beep boop, beep beep boop.", ephemeral=True)

        questions = await self.fetch_trivia_questions()
        question = questions[0]

        embed = discord.Embed(
            description=f"You've been challenged to a game of trivia by {ctx.author.mention}!",
            color=config["COLORS"]["DEFAULT"],
        )
        embed.add_field(
            name="Category",
            value=question["category"],
            inline=False,
        )

        view = AcceptChallengeView(self, ctx.author, opponent, question)
        await ctx.send(content=opponent.mention, embed=embed, view=view)

        def check(m):
            return (
                m.author.id in [ctx.author.id, opponent.id] and m.channel == ctx.channel
            )

        correct_answer = question["correct_answer"].lower()
        while True:
            try:
                response = await self.bot.wait_for("message", check=check, timeout=30)

                answer_mapping = {"a": 0, "b": 1, "c": 2, "d": 3}
                user_answer = response.content.lower().strip()

                if question["type"] == "multiple":
                    choices = [question["correct_answer"].lower()] + [
                        a.lower() for a in question["incorrect_answers"]
                    ]
                    if user_answer in [
                        "a",
                        "b",
                        "c",
                        "d",
                    ]:
                        if choices[answer_mapping[user_answer]] == correct_answer:
                            await ctx.send(
                                f"Congratulations {response.author.mention}, you've won!"
                            )
                            await self.update_winner_score(
                                str(response.author.id), question["category"]
                            )
                            break
                        else:
                            await ctx.send("That's incorrect! Try again.")
                    else:
                        await ctx.send("Invalid option. Try again.")

                elif question["type"] == "boolean":
                    if (user_answer == "t" and correct_answer == "true") or (
                        user_answer == "f" and correct_answer == "false"
                    ):
                        await ctx.send(
                            f"Congratulations {response.author.mention}, you've won!"
                        )
                        await self.update_winner_score(
                            str(response.author.id), question["category"]
                        )
                        break
                    else:
                        await ctx.send("That's incorrect! Try again.")

            except asyncio.TimeoutError:
                await ctx.send("Time's up! No one answered in time.")
                break

        if response.content.lower() != correct_answer:
            await ctx.send(f"The correct answer was {question['correct_answer']}.")

    @_trivia.command(
        name="stats",
        description="View your trivia stats.",
    )
    async def stats(
        self,
        ctx: discord.ApplicationContext,
    ):
        user_id = str(ctx.author.id)
        query = "SELECT category, SUM(wins) as total_wins FROM trivia_winners WHERE user_id = ? GROUP BY category"
        params = (user_id,)

        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        if rows:
            total_wins = sum(row[1] for row in rows)
            top_category = max(rows, key=lambda row: row[1])

            embed = discord.Embed(
                color=config["COLORS"]["SUCCESS"],
            )
            embed.add_field(name="Total Wins", value=str(total_wins))
            embed.add_field(
                name="Top Category",
                value=f"{top_category[0]} ({top_category[1]})",
            )
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("No trivia wins found for you!", ephemeral=True)


def setup(bot_: discord.Bot):
    bot_.add_cog(Trivia(bot_))
