from redbot.core import commands, Config
import discord


class PublicRooms(commands.Cog):
    """Automatic Public VC Creation"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=14000605, force_registration=True)
        default_guild = {
            "toggle": False,
            "systems": {},
        }
        self.config.register_guild(**default_guild)
        self.bot.loop.create_task(self.initialize())

    async def initialize(self) -> None:
        await self.bot.wait_until_red_ready()
        all_guilds = await self.config.all_guilds()
        for g in all_guilds.keys():
            async with self.config.guild_from_id(g).all() as guild:
                for sys in guild['systems'].values():
                    for a in sys['active']:
                        try:
                            vc = self.bot.get_channel(a[0])
                            if not vc.members:
                                await vc.delete(reason="PublicRooms: unused VC after cog load")
                                sys['active'].remove(a)
                        except (AttributeError, discord.NotFound, discord.HTTPException, discord.Forbidden, discord.InvalidData):
                            sys['active'].remove(a)

    @commands.Cog.listener("on_voice_state_update")
    async def _voice_listener(self, member: discord.Member, before, after):

        if (
            not await self.config.guild(member.guild).toggle() or  # PublicRooms toggled off
            member.bot or  # Member is a bot
            await self.bot.cog_disabled_in_guild(self, member.guild)  # Cog disabled in guild
        ):
            return

        leftroom = False
        joinedroom = False

        # Moved channels
        if before.channel and after.channel:
            async with self.config.guild(member.guild).systems() as systems:
                for sys in systems.values():
                    if not sys['toggle']:
                        continue

                    active = [x[0] for x in sys['active']]

                    # Member joined an active PublicRoom
                    if sys['log_channel'] and before.channel.id not in active and after.channel.id in active:
                        await member.guild.get_channel(sys['log_channel']).send(
                            f'{member.mention} joined `{after.channel.name}`',
                            allowed_mentions=discord.AllowedMentions.none()
                        )

                    # Member left a PublicRoom
                    if before.channel.id in active and before.channel.id != after.channel.id:
                        leftroom = True

                    # Member went into the origin channel
                    if sys['origin'] == after.channel.id != before.channel.id:
                        joinedroom = True

                    if leftroom and joinedroom:
                        break

        # Left a channel
        if (before.channel and not after.channel) or leftroom:
            async with self.config.guild(member.guild).systems() as systems:
                for sys in systems.values():
                    # Skip system if not toggled on
                    if not sys['toggle']:
                        continue

                    for a in sys['active']:
                        if not a[0] == before.channel.id:
                            continue

                        # Everyone left channel
                        if not before.channel.members:
                            sys['active'].remove(a)
                            await before.channel.delete(reason="PublicRooms: all users have left")
                            if sys['log_channel']:
                                await member.guild.get_channel(sys['log_channel']).send(
                                    f'{member.mention} left `{before.channel.name}`, channel removed',
                                    allowed_mentions=discord.AllowedMentions.none()
                                )
                            break

                        # Member with custom channel name left
                        if sys['overrides'].get(str(member.id)) == before.channel.name :
                            # Find correct position of new channel
                            no_created = False
                            no_missing = False
                            all_nums = [x[1] for x in sys['active'] if x[1] != 0]
                            try:
                                num = list(set(range(1, max(all_nums) + 1)) - set(all_nums))[0]
                                for i in sorted(sys['active'], key=lambda x: x[1]):
                                    if i[1] > num:
                                        ch = i[0]
                                        break
                                position = member.guild.get_channel(ch).position - 1
                            except IndexError:
                                num = max(all_nums) + 1
                                no_missing = True
                            except ValueError:
                                no_created = True

                            if no_created or no_missing:
                                if no_created:
                                    num = 1
                                public_vc = await before.channel.edit(
                                    name=sys['channel_name'].replace("{num}", str(num)),
                                    reason=f"PublicRooms: {member.display_name} left room with custom name",
                                )
                            else:
                                public_vc = await before.channel.edit(
                                    name=sys['channel_name'].replace("{num}", str(num)),
                                    position=position,
                                    reason=f"PublicRooms: {member.display_name} left room with custom name",
                                )

                            if sys['log_channel']:
                                await member.guild.get_channel(sys['log_channel']).send(
                                    f'{member.mention} left `{before.channel.name}`, renamed to {public_vc.name}',
                                    allowed_mentions=discord.AllowedMentions.none()
                                )

                            break

                        # Log user leaving
                        if sys['log_channel']:
                            await member.guild.get_channel(sys['log_channel']).send(
                                f'{member.mention} left `{before.channel.name}`',
                                allowed_mentions=discord.AllowedMentions.none()
                            )
                            break

        # Joined a channel
        if (not before.channel and after.channel) or joinedroom:
            async with self.config.guild(member.guild).systems() as systems:
                for sys in systems.values():

                    # Joined an Origin channel of a system that is toggled on
                    if sys['toggle'] and sys['origin'] == after.channel.id:
                        # Create the new VC

                        channel_name = sys['overrides'].get(str(member.id))
                        if channel_name:
                            num = 0
                            public_vc = await member.guild.create_voice_channel(
                                name=channel_name,
                                category=after.channel.category,
                                position=after.channel.position+1,
                                bitrate=min(sys['bitrate'] * 1000, member.guild.bitrate_limit),
                                reason=f"PublicRooms: created by {member.display_name}",
                            )
                        else:
                            # Find correct position of new channel
                            no_created = False
                            no_missing = False
                            all_nums = [x[1] for x in sys['active']]
                            try:
                                num = list(set(range(1, max(all_nums) + 1)) - set(all_nums))[0]
                                for i in sorted(sys['active'], key=lambda x: x[1]):
                                    if i[1] > num:
                                        ch = i[0]
                                        break
                                position = member.guild.get_channel(ch).position - 1
                            except IndexError:
                                num = max(all_nums) + 1
                                no_missing = True
                            except ValueError:
                                no_created = True

                            if no_created or no_missing:
                                if no_created:
                                    num = 1
                                public_vc = await member.guild.create_voice_channel(
                                    name=sys['channel_name'].replace("{num}", str(num)),
                                    category=after.channel.category,
                                    bitrate=min(sys['bitrate']*1000, member.guild.bitrate_limit),
                                    reason=f"PublicRooms: created by {member.display_name}",
                                )
                            else:
                                public_vc = await member.guild.create_voice_channel(
                                    name=sys['channel_name'].replace("{num}", str(num)),
                                    category=after.channel.category,
                                    position=position,
                                    bitrate=min(sys['bitrate'] * 1000, member.guild.bitrate_limit),
                                    reason=f"PublicRooms: created by {member.display_name}",
                                )

                        # Move creator to their new room
                        await member.move_to(public_vc, reason="PublicRooms: is VC creator")

                        # If log channel set, then send logs
                        if sys['log_channel']:
                            await member.guild.get_channel(sys['log_channel']).send(
                                f'{member.mention} created `{public_vc.name}`',
                                allowed_mentions=discord.AllowedMentions.none()
                            )

                        # Add to active list
                        sys['active'].append((public_vc.id, num))

                        break

                    # Member joined an active PublicRoom
                    elif sys['toggle'] and sys['log_channel'] and after.channel.id in [x[0] for x in sys['active']]:
                        await member.guild.get_channel(sys['log_channel']).send(
                            f'{member.mention} joined `{after.channel.name}`',
                            allowed_mentions=discord.AllowedMentions.none()
                        )

        return

    @commands.guild_only()
    @commands.admin()
    @commands.group(name="publicrooms")
    async def _publicrooms(self, ctx: commands.Context):
        """Set Up Public VC Systems"""

    @_publicrooms.command(name="toggle")
    async def _toggle(self, ctx: commands.Context, true_or_false: bool):
        """Toggle PublicRooms in this server."""
        await self.config.guild(ctx.guild).toggle.set(true_or_false)
        return await ctx.tick()

    @_publicrooms.command(name="add")
    async def _add(self, ctx: commands.Context, system_name: str, origin_channel: discord.VoiceChannel, default_bitrate_in_kbps: int, *, channel_name_template: str):
        """
        Add a new PublicRooms system in this server.

        For the `channel_name_template`, enter a string, with `{num}` contained if you want it to be replaced with the number of active VCs.
        """

        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name in systems.keys():
                return await ctx.send("There is already a PublicRooms system with that name!")

            systems[system_name] = {
                "toggle": True,
                "origin": origin_channel.id,
                "bitrate": default_bitrate_in_kbps,
                "channel_name": channel_name_template,
                "log_channel": None,
                "active": [],
                "overrides": {}
            }

        return await ctx.send(f'A new PublicRooms system with origin channel `{origin_channel.name}` has been created and toggled on. If you would like to toggle it or set a log channel, please use `{ctx.clean_prefix}publicrooms edit logchannel {system_name}`.')

    @_publicrooms.group(name="edit")
    async def _edit(self, ctx: commands.Context):
        """Edit a PublicRooms System"""

    @_edit.command(name="toggle")
    async def _edit_toggle(self, ctx: commands.Context, system_name: str, true_or_false: bool):
        """Toggle a PublicRooms system in this server."""
        async with self.config.guild(ctx.guild).systems() as systems:
            systems[system_name]["toggle"] = true_or_false
        return await ctx.tick()

    @_edit.command(name="origin")
    async def _edit_origin(self, ctx: commands.Context, system_name: str, origin_channel: discord.VoiceChannel):
        """Edit the Origin channel for a PublicRooms system in this server."""

        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name not in systems.keys():
                return await ctx.send("There was no PublicRooms system found with that name!")

            systems[system_name]["origin"] = origin_channel.id

        return await ctx.tick()

    @_edit.command(name="bitrate")
    async def _edit_bitrate(self, ctx: commands.Context, system_name: str, bitrate_in_kbps: int):
        """Edit the new VC bitrate (in kbps) for a PublicRooms system in this server."""

        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name not in systems.keys():
                return await ctx.send("There was no PublicRooms system found with that name!")

            systems[system_name]["bitrate"] = bitrate_in_kbps

        return await ctx.tick()

    @_edit.command(name="name")
    async def _edit_name(self, ctx: commands.Context, system_name: str, *, channel_name_template: str):
        """
        Edit the channel name template for a PublicRooms system in this server.

        Enter a string, with `{num}` contained if you want it to be replaced with the number of active VCs.
        """

        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name not in systems.keys():
                return await ctx.send("There was no PublicRooms system found with that name!")

            systems[system_name]["channel_name"] = channel_name_template

        return await ctx.tick()

    @_edit.command(name="logchannel")
    async def _edit_log_channel(self, ctx: commands.Context, system_name: str, channel: discord.TextChannel = None):
        """Edit the log channel for a PublicRooms system in this server (leave blank to set to None)."""

        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name not in systems.keys():
                return await ctx.send("There was no PublicRooms system found with that name!")

            if channel:
                systems[system_name]["log_channel"] = channel.id
            else:
                systems[system_name]["log_channel"] = None

        return await ctx.tick()

    @_publicrooms.command(name="remove", aliases=["delete"])
    async def _remove(self, ctx: commands.Context, system_name: str, enter_true_to_confirm: bool):
        """Remove a PublicRooms system in this server."""

        if not enter_true_to_confirm:
            return await ctx.send("Please provide `true` as the parameter to confirm.")

        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name not in systems.keys():
                return await ctx.send("There was no PublicRooms system found with that name!")

            del systems[system_name]

        return await ctx.send(f"The PublicRooms system `{system_name}` was removed.")

    @_publicrooms.command(name="clearactive")
    async def _clear_active(self, ctx: commands.Context, system_name: str, enter_true_to_confirm: bool):
        """Clears the cache of current active PublicRooms."""

        if not enter_true_to_confirm:
            return await ctx.send("Please provide `true` as the parameter to confirm.")

        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name not in systems.keys():
                return await ctx.send("There was no PublicRooms system found with that name!")

            systems[system_name]["active"] = []

        return await ctx.send(f"The active rooms in `{system_name}` were cleared.")

    @_edit.group(name="custom")
    async def _custom(self, ctx: commands.Context):
        """Custom Channel Names for Specific Members"""

    @_custom.command(name="add")
    async def _custom_add(self, ctx: commands.Context, system_name: str, member: discord.Member, *, channel_name: str):
        """Add a custom channel name override for a specific member."""
        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name not in systems.keys():
                return await ctx.send("There was no PublicRooms system found with that name!")

            systems[system_name]["overrides"][member.id] = channel_name
        return await ctx.tick()

    @_custom.command(name="remove", aliases=["delete"])
    async def _custom_remove(self, ctx: commands.Context, system_name: str, member: discord.Member):
        """Remove a custom channel name override for a specific member."""
        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name not in systems.keys():
                return await ctx.send("There was no PublicRooms system found with that name!")

            try:
                del systems[system_name]["overrides"][str(member.id)]
            except KeyError:
                return await ctx.send("This member did not have a custom channel name override!")
        return await ctx.tick()

    @_custom.command(name="list")
    async def _custom_list(self, ctx: commands.Context, system_name: str):
        """List the custom channel name overrides for a PublicRooms system."""
        overrides = ""
        async with self.config.guild(ctx.guild).systems() as systems:
            if system_name not in systems.keys():
                return await ctx.send("There was no PublicRooms system found with that name!")

            for user, name in systems[system_name]["overrides"].items():
                overrides += f"{(await self.bot.get_or_fetch_member(ctx.guild, int(user))).mention}: {name}\n"
        if not overrides:
            return await ctx.send("No custom channel name overrides found for this system.")
        return await ctx.send(overrides)

    @_publicrooms.command(name="view")
    async def _view(self, ctx: commands.Context):
        """View the PublicRooms settings in this server."""

        settings = await self.config.guild(ctx.guild).all()
        embed = discord.Embed(title="PublicRooms Settings", color=await ctx.embed_color(), description=f"""
        **Server Toggle:** {settings['toggle']}
        {"**Systems:** None" if not settings['systems'] else ""}
        """)

        for name, system in settings['systems'].items():
            embed.add_field(name=f"System `{name}`", inline=False, value=f"""
            **Toggle:** {system['toggle']}
            **Origin:** {ctx.guild.get_channel(system['origin']).name}
            **BitRate:** {system['bitrate']} kbps
            **Name Template:** {system['channel_name']}
            **Log Channel:** {ctx.guild.get_channel(system['log_channel']).mention if system['log_channel'] else None}
            """)

        return await ctx.send(embed=embed)
