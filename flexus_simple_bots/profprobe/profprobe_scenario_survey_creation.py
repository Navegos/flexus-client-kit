import asyncio
import json
import logging

from flexus_simple_bots.profprobe import profprobe_bot
from flexus_simple_bots.profprobe.integrations import survey_monkey_mock
from flexus_client_kit import ckit_scenario_setup, ckit_bot_query
from flexus_client_kit.integrations import fi_pdoc

logger = logging.getLogger("scenario")

profprobe_bot.survey_monkey.aiohttp = survey_monkey_mock.MockAiohttp()


async def create_test_survey_pdoc(pdoc_integration, survey_name):
    survey_data = {
        "title": f"Customer Satisfaction Survey - {survey_name}",
        "description": "Help us improve our product",
        "questions": [
            {
                "question": "How satisfied are you with our product?",
                "type": "rating_scale",
                "scale_min": 1,
                "scale_max": 5,
                "required": True
            },
            {
                "question": "Would you recommend us to a friend?",
                "type": "nps",
                "required": True
            },
            {
                "question": "What features do you use most?",
                "type": "multiple_choice",
                "choices": ["Dashboard", "Reports", "API", "Mobile App"],
                "required": False
            },
            {
                "question": "Any additional feedback?",
                "type": "open_ended",
                "required": False
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
        group_prefix="scenario-survey-creation"
    )
    
    survey_monkey_mock.clear_mock_data()
    
    pdoc_integration = fi_pdoc.IntegrationPdoc(setup.fclient, setup.fgroup_id)
    
    survey_name = "test-satisfaction-2024"
    pdoc_path = await create_test_survey_pdoc(pdoc_integration, survey_name)
    logger.info(f"Created test survey pdoc at {pdoc_path}")
    
    await setup.post_user_message_and_wait_reply(
        f"Please create a SurveyMonkey survey from the pdoc at {pdoc_path}"
    )
    
    survey_created_msg = await setup.wait_for_toolcall("create_surveymonkey_survey", None, {"pdoc_path": pdoc_path})
    
    doc = await pdoc_integration.pdoc_cat(pdoc_path)
    content = json.loads(doc.pdoc_content)
    
    assert "meta" in content, "Meta field not added to pdoc"
    assert "survey_id" in content["meta"], "Survey ID not saved in pdoc"
    assert "survey_url" in content["meta"], "Survey URL not saved in pdoc"
    
    survey_id = content["meta"]["survey_id"]
    assert survey_id in survey_monkey_mock.mock_surveys, f"Survey {survey_id} not found in mock data"
    
    mock_survey = survey_monkey_mock.mock_surveys[survey_id]
    assert mock_survey["title"] == f"Customer Satisfaction Survey - {survey_name}"
    assert len(mock_survey["pages"][0]["questions"]) == 4
    
    logger.info(f"✅ Survey created successfully with ID: {survey_id}")
    print(f"Survey URL: {content['meta']['survey_url']}")


if __name__ == "__main__":
    setup = ckit_scenario_setup.ScenarioSetup("profprobe")
    asyncio.run(setup.run_scenario(scenario))
