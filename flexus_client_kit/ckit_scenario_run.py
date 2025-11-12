import argparse
import json
import logging
import os
import subprocess
from typing import Optional

import gql

from flexus_client_kit import ckit_bot_query, ckit_client, ckit_scenario_setup
from flexus_super_bots import run_dev_bots_in_ws

logger = logging.getLogger("scenario_run")


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


async def run_scenario_from_trajectory(
    trajectory_json_path: str,
    persona_marketable_name: str,
    persona_setup: Optional[dict] = None,
) -> None:
    scenario = ckit_scenario_setup.ScenarioSetup(service_name="trajectory_replay")

    scenario.bs = await ckit_client.query_basic_stuff(scenario.fclient)
    scenario.ws = await ckit_scenario_setup.select_workspace_for_scenario(scenario.fclient, scenario.bs, persona_marketable_name)
    await scenario.create_test_group(group_prefix="trajectory")
    await scenario.hire_bot(persona_marketable_name, None, persona_setup or {})
    logger.info("Trajectory scenario setup completed in group %s", scenario.fgroup_name)

    superpassword = await run_dev_bots_in_ws.get_superpassword(scenario.fclient.base_url_http, None)
    logger.info(f"Starting bot {scenario.persona.persona_name} for trajectory replay")
    bot_process = run_dev_bots_in_ws.start_bot_process(scenario.persona, scenario.ws.ws_id, superpassword)

    ft_id: Optional[str] = None
    try:
        while True:
            user_message = await scenario_generate_user_message(
                scenario.fclient,
                trajectory_json_path,
                scenario.fgroup_id,
                ft_id,
            )
            logger.info(f"Generated user message: {user_message}")

            if user_message == "SCENARIO_DONE":
                logger.info("Trajectory completed successfully!")
                break

            if not ft_id:
                async with (await scenario.fclient.use_http()) as http:
                    bot_result = await http.execute(gql.gql("""
                        mutation BotActivate($persona_id: String!, $first_question: String!, $activation_type: String!) {
                            bot_activate(
                                who_is_asking: "trajectory_scenario",
                                persona_id: $persona_id,
                                activation_type: $activation_type,
                                first_question: $first_question,
                                title: "Trajectory Test",
                                first_calls: "null"
                            ) {
                                ft_id
                            }
                        }"""),
                        variable_values={
                            "persona_id": scenario.persona.persona_id,
                            "first_question": user_message,
                            "activation_type": "default"
                        }
                    )
                ft_id = bot_result["bot_activate"]["ft_id"]
                logger.info(f"Created thread {ft_id}")
            else:
                async with (await scenario.fclient.use_http()) as http:
                    await http.execute(gql.gql("""
                        mutation SendMessage($input: FThreadMultipleMessagesInput!) {
                            thread_messages_create_multiple(input: $input)
                        }"""),
                        variable_values={
                            "input": {
                                "ftm_belongs_to_ft_id": ft_id,
                                "messages": [{
                                    "ftm_belongs_to_ft_id": ft_id,
                                    "ftm_alt": 100,
                                    "ftm_num": -1,
                                    "ftm_prev_alt": 100,
                                    "ftm_role": "user",
                                    "ftm_content": json.dumps(user_message),
                                    "ftm_call_id": "",
                                    "ftm_provenance": json.dumps({"system": "trajectory_scenario"}),
                                }]
                            }
                        }
                    )

            threads_data = await ckit_bot_query.wait_until_bot_threads_stop(
                scenario.bot_fclient, scenario.persona, scenario.inprocess_tools, only_ft_id=ft_id, timeout=120
            )
            logger.info(f"Bot finished processing, thread state: {threads_data.get(ft_id)}")

    finally:
        bot_process.terminate()
        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_process.kill()

        await scenario.print_personas_ktasks_and_threads()
        if scenario.should_cleanup:
            await scenario.cleanup()
            logger.info("Cleanup completed.")
        else:
            logger.info("Skipping cleanup (--no-cleanup flag set)")
