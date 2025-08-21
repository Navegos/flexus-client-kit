# flexus.agency
# flexus.bot
# flexus.team
# flexus.store

import asyncio
import logging
import json
from typing import List, Optional, Dict, Any

import discord
from discord.ext import commands
import gql
from gql import client as gql_client
from gql.transport.aiohttp import AIOHTTPTransport

from flexus_client_kit import ckit_client, gql_utils

from flexus_backend.db_connections import env
from dataclasses import dataclass


logger = logging.getLogger("karen")

USE_ONLY_ALT = 100


@dataclass
class TechSupportSettingsOutput:
    support_channel_list: List[str]
    support_discord_key: str
    support_fgroup_id: str
    support_fuser_id: str
    support_api_key: str

@dataclass
class FThread:
    located_fgroup_id: str
    ft_id: str
    ft_app_searchable: str
    ft_error: Optional[str]

@dataclass
class FThreadMessage:
    ftm_belongs_to_ft_id: str
    ftm_alt: int
    ftm_num: int
    ftm_prev_alt: Optional[int]
    ftm_role: str
    ftm_content: str
    ftm_app_specific: Any    # Only exists for messages this bot creates, not for assistant messages
    ftm_user_preferences: Any
    ft_app_searchable: Optional[str] = None   # Arrives with subscription, but not when using _list(), bot identifies the thread by it

@dataclass
class TechSupportSettingSubs:
    news_action: str
    ws_id: str
    pubsub: str
    settings: Optional[TechSupportSettingsOutput]
    thread_message: Optional[FThreadMessage]


class BotPerWorkspace:
    def __init__(self, ws_id: str, settings: TechSupportSettingsOutput, http_session: gql_client.ReconnectingAsyncClientSession):
        self.ws_id = ws_id
        self.settings = settings
        self.http_session = http_session
        self.bot: Optional[commands.Bot] = None

    async def recall_thread_by_id(self, ft_id: str) -> FThread:
        resp = await self.http_session.execute(gql.gql(f"""
            query TechSupportGetThread($id: String!) {{
                thread_get(id: $id) {{
                    {gql_utils.gql_fields(FThread)}
                }}
            }}"""),
            variable_values={"id": ft_id},
        )
        return gql_utils.dataclass_from_dict(resp["thread_get"], FThread)

    async def recall_thread_by_searchable(
        self,
        located_fgroup_id: str,
        ft_app_searchable: str,
    ) -> List[FThread]:
        resp = await self.http_session.execute(gql.gql(f"""
            query TechSupportRecallThread($located_fgroup_id: String!, $ft_app_searchable: String!) {{
                threads_app_captured(located_fgroup_id: $located_fgroup_id, ft_app_searchable: $ft_app_searchable, ft_app_capture: "tech_support_bot") {{
                    {gql_utils.gql_fields(FThread)}
                }}
            }}"""),
            variable_values={"located_fgroup_id": located_fgroup_id, "ft_app_searchable": ft_app_searchable},
        )
        return [
            gql_utils.dataclass_from_dict(x, FThread)
            for x in resp["threads_app_captured"]
        ]

    async def create_fthread(
        self,
        ft_title: str,
        located_fgroup_id: str,
        ft_app_searchable: str,
    ) -> FThread:
        resp = await self.http_session.execute(gql.gql(f"""
            mutation CreateFThread($input: FThreadInput!) {{
                thread_create(input: $input) {{
                    {gql_utils.gql_fields(FThread)}
                }}
            }}"""),
            variable_values={
                "input": {
                    "owner_shared": True,
                    "located_fgroup_id": located_fgroup_id,
                    "ft_subchat_dest_ft_id": None,
                    "ft_fexp_id": "tech_support_karen:0.1",
                    "ft_title": ft_title,
                    "ft_app_capture": "tech_support_bot",
                    "ft_app_searchable": ft_app_searchable,
                }
            },
        )
        return gql_utils.dataclass_from_dict(resp["thread_create"], FThread)

    async def recall_messages(self, ft_id: str) -> List[FThreadMessage]:
        resp = await self.http_session.execute(gql.gql(f"""
            query TechSupportRecallMsgs($ft_id: String!) {{
                thread_messages_list(ft_id: $ft_id) {{
                    {gql_utils.gql_fields(FThreadMessage)}
                }}
            }}"""),
            variable_values={"ft_id": ft_id},
        )
        return [gql_utils.dataclass_from_dict(x, FThreadMessage) for x in resp["thread_messages_list"]]

    async def sync_discord_thread_to_db(self, dthread: discord.Thread, bot_user: discord.ClientUser) -> None:
        fthreads = await self.recall_thread_by_searchable(self.settings.support_fgroup_id, "support_bot:%s" % dthread.id)
        if len(fthreads) == 1:
            fthread = fthreads[0]
        elif len(fthreads) == 0:
            fthread = await self.create_fthread(
                located_fgroup_id=self.settings.support_fgroup_id,
                ft_title=dthread.name,
                ft_app_searchable=("support_bot:%s" % dthread.id),
            )
        else:
            assert 0
        db_msgs = await self.recall_messages(fthread.ft_id)
        known = {}
        n = 0
        for m in db_msgs:
            if m.ftm_alt == USE_ONLY_ALT and m.ftm_num > n:
                n = m.ftm_num
            if m.ftm_app_specific:
                j = m.ftm_app_specific
                if isinstance(j, dict) and j.get("discord_id"):
                    known[str(j["discord_id"])] = True
        n += 1   # starts with 1 if no messages yes, zero is the system prompt
        msgs = []
        async for m in dthread.history(limit=None, oldest_first=True):
            # print("AAAAAAA history", m)
            if m.author == bot_user:
                continue
            # AAAAAAA history <Message id=1378031357804154900 channel=<Thread id=1378031356453589073 name='Support 1340' parent=support_bot owner_id=1356973954627145779 locked=False archived=False> type=<MessageType.thread_starter_message: 21> author=<Member id=1356973954627145779 name='Karen (support 🤖)' global_name=None bot=True nick=None guild=<Guild id=1037660742440194089 name='Refact AI' shard_id=0 chunked=False member_count=1718>> flags=<MessageFlags value=0>>
            # AAAAAAA history <Message id=1378031358823239761 channel=<Thread id=1378031356453589073 name='Support 1340' parent=support_bot owner_id=1356973954627145779 locked=False archived=False> type=<MessageType.default: 0> author=<Member id=1356973954627145779 name='Karen (support 🤖)' global_name=None bot=True nick=None guild=<Guild id=1037660742440194089 name='Refact AI' shard_id=0 chunked=False member_count=1718>> flags=<MessageFlags value=0>>
            # AAAAAAA history <Message id=1378031385922768997 channel=<Thread id=1378031356453589073 name='Support 1340' parent=support_bot owner_id=1356973954627145779 locked=False archived=False> type=<MessageType.default: 0> author=<User id=1049343460353790022 name='refactai.olegklimov' global_name='Oleg Klimov' bot=False> flags=<MessageFlags value=0>>
            # AAAAAAA history <Message id=1378031458760786071 channel=<Thread id=1378031356453589073 name='Support 1340' parent=support_bot owner_id=1356973954627145779 locked=False archived=False> type=<MessageType.default: 0> author=<User id=1049343460353790022 name='refactai.olegklimov' global_name='Oleg Klimov' bot=False> flags=<MessageFlags value=0>>
            mid = str(m.id)
            if mid in known:
                continue

            content = m.content
            if m.type == discord.MessageType.thread_starter_message:
                try:
                    starter_message = await dthread.parent.fetch_message(dthread.id)
                    content = starter_message.content
                except Exception as e:
                    print(f"Failed to fetch starter message: {e}")
                    continue

            # print("AAAAAAA have content %r" % content)
            if not content:
                continue

            logger.info("👤 ws_id=%r dthread=%r sync to db %r", self.ws_id, str(dthread.id), content)
            msgs.append({
                "ftm_belongs_to_ft_id": fthread.ft_id,
                "ftm_alt": USE_ONLY_ALT,
                "ftm_num": n,
                "ftm_prev_alt": USE_ONLY_ALT,
                "ftm_role": "user",
                "ftm_content": json.dumps(content) if content else "null",
                "ftm_tool_calls": "null",
                "ftm_call_id": "",
                "ftm_usage": "null",
                "ftm_user_preferences": json.dumps({
                    "model": "gpt-4.1-mini",
                    "max_new_tokens": 4096,
                    "n": 1,
                }),
                "ftm_app_specific": json.dumps({"discord_id": mid, "tech_support_bot": True}),
                "ftm_provenance": json.dumps({
                    "system_type": "service_tech_support_bot",
                    "version": "0.1",
                }),
            })
            n += 1

        if msgs:
            await self.http_session.execute(gql.gql("""
                mutation TechSupportCreateMultiple($input: FThreadMultipleMessagesInput!) {
                    thread_messages_create_multiple(input: $input)
                }"""),
                variable_values={
                    "input": {
                        "ftm_belongs_to_ft_id": fthread.ft_id,
                        "messages": msgs,
                    }
                },
            )

    def create_bot(self) -> commands.Bot:
        logger.info("Coroutine started, discord key=...%s channels=%s" % (self.settings.support_discord_key[-4:], self.settings.support_channel_list))
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix="!", intents=intents)

        @bot.event
        async def on_ready() -> None:
            print(f"Logged in as {bot.user.name!r} for ws_id={self.ws_id!r}")

        @bot.event
        async def on_message(message: discord.Message) -> None:
            if message.author == bot.user:
                return

            if isinstance(message.channel, discord.TextChannel) and message.channel.name in self.settings.support_channel_list:
                guys_name = message.author.global_name
                discord_thread: discord.Thread = await message.create_thread(name="Support 1342")
                await discord_thread.send("Hi %s, I'm a tech support bot." % guys_name)
                await self.sync_discord_thread_to_db(discord_thread, bot.user)

            elif isinstance(message.channel, discord.Thread):
                discord_thread: discord.Thread = message.channel
                await self.sync_discord_thread_to_db(discord_thread, bot.user)

            else:
                logger.error("Don't know what to do with %s" % type(message.channel))

        return bot

    async def repost_assistant_message_to_discord(self, thread_message: FThreadMessage) -> None:
        import re
        m = re.match(r"^support_bot:(\d+)$", thread_message.ft_app_searchable)
        if not m:
            logger.error("Hmm no support_bot:1234567890 in ft_app_searchable: %s", thread_message)
            return
        thread_discord_id1 = m.group(1)
        thread = await self.recall_thread_by_id(thread_message.ftm_belongs_to_ft_id)
        m = re.match(r"^support_bot:(\d+)$", thread.ft_app_searchable)
        if not m:
            logger.error("Hmm no support_bot:1234567890 in thread.ft_app_searchable: %s", thread)
            return
        thread_discord_id2 = m.group(1)
        if thread_discord_id1 != thread_discord_id2:
            logger.error("WTF different thread_discord_id1=%s and thread_discord_id2=%s" % (thread_discord_id1, thread_discord_id2))
            return

        try:
            channel: Any = self.bot.get_channel(int(thread_discord_id1))   # might be GuildChannel, Thread, PrivateChannel
            if channel is None:
                channel = await self.bot.fetch_channel(int(thread_discord_id1))   # same
        except Exception as e:
            logger.error("Discord library fails (1), thread_discord_id=%s: %s", thread_discord_id1, e)
            return

        # XXX maybe patch message in db with ftm_app_specific = {"discord_id": thread_discord_id1, "tech_support_bot": True} ?
        if isinstance(channel, discord.Thread):
            txt = thread_message.ftm_content
            try:
                logger.info("🤖 ws_id=%r dthread=%r sending %r", self.ws_id, thread_discord_id1, txt)
                await channel.send(txt)
            except Exception as e:
                logger.error("Discord library fails (2), thread_discord_id=%s: %s", thread_discord_id1, e)



ws2bot: Dict[str, BotPerWorkspace] = {}

async def run_until_cancelled(ws_id: str, settings: TechSupportSettingsOutput) -> None:
    http_transport = AIOHTTPTransport(
        url="http://localhost:8008/v1/graphql",
        headers={"Authorization": f"Bearer {settings.support_api_key}"},
    )
    http_client = gql.Client(transport=http_transport, fetch_schema_from_transport=True)
    try:
        async with http_client as http_session:
            tech_support_bot = BotPerWorkspace(ws_id, settings, http_session)
            tech_support_bot.bot = tech_support_bot.create_bot()
            ws2bot[tech_support_bot.ws_id] = tech_support_bot
            await tech_support_bot.bot.start(tech_support_bot.settings.support_discord_key)
    except asyncio.CancelledError:
        pass
    finally:
        if ws_id in ws2bot:
            tech_support_bot = ws2bot[ws_id]
            if tech_support_bot.bot is not None and not tech_support_bot.bot.is_closed():
                logger.info("Dropping discord library handle for ws_id=%s", ws_id)
                await tech_support_bot.bot.close()
            ws2bot.pop(ws_id, None)


async def react_to_stuff_happening_in_the_database() -> None:
    await env.slow_env_init(
        want_fastapi=False,
        want_prisma=False,
        want_embedding=False,
        want_binstorage=False,
    )
    subscription = gql.gql(f"""
        subscription TechSupportSettingsSubs {{
            everything_a_tech_support_bot_needs_to_know {{
                {gql_utils.gql_fields(TechSupportSettingSubs)}
            }}
        }}""")
    async_tasks: Dict[str, asyncio.Task] = {}
    client = ckit_client.FlexusClient("tech_support_bot")
    ws_client = await client.use_ws()
    async with ws_client as session:
        async for result in session.subscribe(subscription):
            subs = gql_utils.dataclass_from_dict(result["everything_a_tech_support_bot_needs_to_know"], TechSupportSettingSubs)
            ws_id = subs.ws_id
            # print("XXX", result)

            if subs.settings:
                assert subs.pubsub == "setting$tech_support_settings"
                existing_task = async_tasks.get(ws_id)
                if existing_task and not existing_task.done():
                    logger.info("To restart, stopping existing bot for ws_id=%r", ws_id)
                    existing_task.cancel()
                    try:
                        await existing_task
                    except asyncio.CancelledError:
                        pass
                logger.info("Starting bot for ws_id=%r", ws_id)
                async_tasks[ws_id] = asyncio.create_task(run_until_cancelled(ws_id, subs.settings))

            elif subs.news_action == "DELETE" and subs.pubsub == "setting$tech_support_settings":
                t = async_tasks.pop(ws_id, None)
                if t:
                    logger.info("Stopping bot for ws_id=%r", ws_id)
                    t.cancel()
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass
            if subs.thread_message and subs.news_action == "INSERT":
                tech_support_bot = ws2bot.get(ws_id)
                if not tech_support_bot:
                    logger.error("Hmm have a message for ws_id=%r but no bot running", ws_id)
                    continue
                if subs.thread_message.ftm_role == "assistant":
                    await tech_support_bot.repost_assistant_message_to_discord(subs.thread_message)


if __name__ == "__main__":
    asyncio.run(react_to_stuff_happening_in_the_database())
