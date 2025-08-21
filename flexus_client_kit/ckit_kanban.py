import json
from dataclasses import dataclass
import dataclasses
from typing import List, Tuple, Optional

import gql

from flexus_client_kit import ckit_client


@dataclass
class FKanbanTaskInput:
    title: str
    state: str
    details_json: Optional[str] = None


async def bot_arrange_kanban_situation(
    client: ckit_client.FlexusClient,
    ws_id: str,
    persona_id: str,
    tasks: List[FKanbanTaskInput],
) -> None:
    http = await client.use_http()
    async with http as h:
        await h.execute(
            gql.gql(
                """mutation ArrangeKanban($ws: String!, $pid: String!, $tasks: [FKanbanTaskInput!]!) {
                    bot_arrange_kanban_situation(ws_id: $ws, persona_id: $pid, tasks: $tasks)
                }""",
            ),
            variable_values={
                "ws": ws_id,
                "pid": persona_id,
                "tasks": [dataclasses.asdict(task) for task in tasks],
            },
        )


async def bot_arrange_kanban_situation2(
    client: ckit_client.FlexusClient,
    ws_id: str,
    persona_id: str,
    tasks: List[Tuple],
) -> None:
    http = await client.use_http()
    tasks_dicts = []
    for task in tasks:
        details = {"fulltext": task[1]}
        tasks_dicts.append({
            "state": task[0],
            "title": task[1][:100],
            "details_json": json.dumps({**details, **task[2]} if len(task) > 2 else details),
        })

    async with http as h:
        await h.execute(
            gql.gql(
                """mutation ArrangeKanban($ws: String!, $pid: String!, $tasks: [FKanbanTaskInput!]!) {
                    bot_arrange_kanban_situation(ws_id: $ws, persona_id: $pid, tasks: $tasks)
                }""",
            ),
            variable_values={
                "ws": ws_id,
                "pid": persona_id,
                "tasks": tasks_dicts,
            },
        )


async def bot_kanban_post_into_inbox(
    client: ckit_client.FlexusClient,
    persona_id: str,
    title: str,
    details_json: str,
) -> None:
    http = await client.use_http()
    async with http as h:
        await h.execute(
            gql.gql(
                """mutation KanbanInbox($pid: String!, $title: String!, $details: String!) {
                    bot_kanban_post_into_inbox(persona_id: $pid, title: $title, details_json: $details)
                }""",
            ),
            variable_values={
                "pid": persona_id,
                "title": title,
                "details": details_json,
            },
        )

