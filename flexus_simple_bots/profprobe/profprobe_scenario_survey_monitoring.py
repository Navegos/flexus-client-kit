import asyncio
import json
import logging
import time

from flexus_simple_bots.profprobe import profprobe_bot
from flexus_simple_bots.profprobe.integrations import survey_monkey_mock
from flexus_client_kit import ckit_scenario_setup, ckit_kanban
from flexus_client_kit.integrations import fi_pdoc

logger = logging.getLogger("scenario")

profprobe_bot.survey_monkey.aiohttp = survey_monkey_mock.MockAiohttp()


async def create_survey_with_meta(pdoc_integration, survey_name, survey_id):
    survey_data = {
        "title": f"Product Feedback - {survey_name}",
        "description": "Quick feedback survey",
        "meta": {
            "survey_id": survey_id,
            "survey_url": f"https://www.surveymonkey.com/r/{survey_id}_collector",
            "collector_id": f"{survey_id}_collector"
        },
        "questions": [
            {
                "question": "How easy was it to use our product?",
                "type": "rating_scale",
                "scale_min": 1,
                "scale_max": 5,
                "required": True
            }
        ]
    }
    
    path = f"/customer-research/unicorn-horn-car-survey-query/{survey_name}"
    await pdoc_integration.pdoc_write(path, json.dumps(survey_data, indent=2), None)
    return path


async def scenario(setup: ckit_scenario_setup.ScenarioSetup) -> None:
    await setup.create_group_hire_and_start_bot(
        persona_marketable_name=profprobe_bot.BOT_NAME,
        persona_marketable_version=profprobe_bot.BOT_VERSION_INT,
        persona_setup={
            "use_surveymonkey": True,
            "SURVEYMONKEY_ACCESS_TOKEN": "test_token_123"
        },
        inprocess_tools=profprobe_bot.TOOLS,
        bot_main_loop=profprobe_bot.profprobe_main_loop,
        group_prefix="scenario-survey-monitoring"
    )
    
    survey_monkey_mock.clear_mock_data()
    
    pdoc_integration = fi_pdoc.IntegrationPdoc(setup.fclient, setup.fgroup_id)
    
    survey_name = "quick-feedback-2024"
    survey_id = "20001"
    
    survey_monkey_mock.mock_surveys[survey_id] = {
        "id": survey_id,
        "title": f"Product Feedback - {survey_name}"
    }
    
    pdoc_path = await create_survey_with_meta(pdoc_integration, survey_name, survey_id)
    logger.info(f"Created survey pdoc with existing survey_id at {pdoc_path}")
    
    mock_responses = [
        {
            "id": "resp_001",
            "response_status": "completed",
            "date_created": "2024-01-15T10:00:00Z",
            "pages": [
                {
                    "questions": [
                        {
                            "headings": [{"heading": "How easy was it to use our product?"}],
                            "answers": [{"text": "4"}]
                        }
                    ]
                }
            ]
        },
        {
            "id": "resp_002",
            "response_status": "completed",
            "date_created": "2024-01-15T11:00:00Z",
            "pages": [
                {
                    "questions": [
                        {
                            "headings": [{"heading": "How easy was it to use our product?"}],
                            "answers": [{"text": "5"}]
                        }
                    ]
                }
            ]
        }
    ]
    
    logger.info("Waiting for bot to check surveys (should happen within 5 minutes)...")
    
    await asyncio.sleep(2)
    survey_monkey_mock.add_mock_responses(survey_id, mock_responses)
    
    kanban_msg = await setup.wait_for_toolcall("bot_kanban_post_into_inbox", None, None, timeout=360)
    
    assert "Process survey results" in str(kanban_msg), "Kanban task not created for survey results"
    
    doc = await pdoc_integration.pdoc_cat(pdoc_path)
    content = json.loads(doc.pdoc_content)
    
    assert content["meta"].get("responses_processed") == True, "Survey not marked as processed"
    
    logger.info(f"✅ Survey monitoring successful - responses detected and kanban task created")
    
    await setup.post_user_message_and_wait_reply(
        f"Get the survey responses for survey_id {survey_id} and save them"
    )
    
    get_responses_msg = await setup.wait_for_toolcall("get_surveymonkey_responses", None, {"survey_id": survey_id})
    
    logger.info("✅ Survey responses retrieved successfully")


if __name__ == "__main__":
    setup = ckit_scenario_setup.ScenarioSetup("profprobe")
    asyncio.run(setup.run_scenario(scenario))
