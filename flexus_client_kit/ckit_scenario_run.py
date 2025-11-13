import json
import logging
import asyncio
from typing import Optional
import gql

from flexus_client_kit import ckit_bot_query, ckit_client, ckit_scenario_setup, ckit_shutdown

logger = logging.getLogger("scena")


async def scenario_generate_user_message(
    client: ckit_client.FlexusClient,
    trajectory_path: str,
    fgroup_id: str,
    ft_id: Optional[str] = None,
):
    with open(trajectory_path, 'r') as f:
        baseline_chat_trajectory = f.read()

    async with (await client.use_http()) as http:
        result = await http.execute(
            gql.gql("""mutation ScenarioGenerateUserMessage(
                $baseline_chat_trajectory: String!,
                $fgroup_id: String!,
                $ft_id: String
            ) {
                scenario_generate_user_message(
                    baseline_chat_trajectory: $baseline_chat_trajectory,
                    fgroup_id: $fgroup_id,
                    ft_id: $ft_id
                )
            }"""),
            variable_values={
                "baseline_chat_trajectory": baseline_chat_trajectory,
                "fgroup_id": fgroup_id,
                "ft_id": ft_id,
            },
        )
    return result["scenario_generate_user_message"]


async def scenario_generate_tool_result_via_model(
    client: ckit_client.FlexusClient,
    fcall_id: str,
    fcall_untrusted_key: str,
    source_file_path: str,
    trajectory_path: str = "",
):
    examples_and_usage_trajectory = ""
    if trajectory_path:
        with open(trajectory_path, 'r') as f:
            examples_and_usage_trajectory = f.read()
    with open(source_file_path, 'r') as f:
        tool_handler_source_code = f.read()

    async with (await client.use_http()) as http:
        await http.execute(
            gql.gql("""mutation ScenarioGenerateToolResult(
                $fcall_id: String!,
                $fcall_untrusted_key: String!,
                $tool_handler_source_code: String!,
                $examples_and_usage_trajectory: String
            ) {
                scenario_generate_tool_result_via_model(
                    fcall_id: $fcall_id,
                    fcall_untrusted_key: $fcall_untrusted_key,
                    tool_handler_source_code: $tool_handler_source_code,
                    examples_and_usage_trajectory: $examples_and_usage_trajectory
                )
            }"""),
            variable_values={
                "fcall_id": fcall_id,
                "fcall_untrusted_key": fcall_untrusted_key,
                "tool_handler_source_code": tool_handler_source_code,
                "examples_and_usage_trajectory": examples_and_usage_trajectory,
            },
        )

