"""
MIT License

Copyright (c) 2021 Obi-Wan3

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import typing
import functools
import googletrans

import discord
from redbot.core import commands

TRANSLATOR = googletrans.Translator()


class Translate(commands.Cog):
    """
    Free Google Translations

    Translate some text using Google Translate for free.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.bot_has_permissions(embed_links=True)
    @commands.command(name="translate")
    async def _translate(self, ctx: commands.Context, language, message: typing.Optional[discord.Message], *, text=None):
        """Translate something (provide either a message ID/link or some text)."""

        if not message and not text:
            return await ctx.send("Please provide either a message ID/link or some text to translate.")

        async with ctx.typing():

            if language.lower() in googletrans.LANGUAGES:
                language = googletrans.LANGUAGES[language.lower()]
            elif language.lower() in ("zh", "ch", "chinese"):
                language = "zh-cn"

            task = functools.partial(TRANSLATOR.translate, text=message.content if message else text, dest=language)

            try:
                res = await self.bot.loop.run_in_executor(None, task)
            except (ValueError, AttributeError):
                failed_embed = discord.Embed(description="Translation failed.", color=discord.Color.red())
                return await ctx.channel.send(embed=failed_embed)

            translated_embed = discord.Embed(title='Translation', color=discord.Color.green())
            translated_embed.add_field(name=googletrans.LANGUAGES[res.src.lower()].title(), value=res.origin, inline=True)
            translated_embed.add_field(name=googletrans.LANGUAGES[res.dest.lower()].title(), value=res.text, inline=True)

        return await ctx.channel.send(embed=translated_embed)
