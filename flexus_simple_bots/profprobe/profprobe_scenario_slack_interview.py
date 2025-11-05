import asyncio
import json
import logging

from flexus_simple_bots.profprobe import profprobe_bot
from flexus_client_kit import ckit_scenario_setup
from flexus_client_kit.integrations import fi_pdoc
from flexus_client_kit.integrations.fi_slack_fake import (
    IntegrationSlackFake,
    fake_slack_instances,
    post_fake_slack_message,
    wait_for_bot_messages,
)

logger = logging.getLogger("scenario")

profprobe_bot.fi_slack.IntegrationSlack = IntegrationSlackFake


async def create_interview_template(pdoc_integration, survey_name):
    interview_data = {
        "title": "User Experience Interview",
        "description": "Interview about product usage and feedback",
        "questions": [
            {
                "question": "What is your primary use case for our product?",
                "type": "open_ended",
                "answer": ""
            },
            {
                "question": "How often do you use the product?",
                "type": "single_choice",
                "choices": ["Daily", "Weekly", "Monthly", "Rarely"],
                "answer": ""
            },
            {
                "question": "What features would you like to see added?",
                "type": "open_ended",
                "answer": ""
            }
        ]
    }
    
    path = f"/customer-research/unicorn-horn-car-survey-query/{survey_name}"
    await pdoc_integration.pdoc_write(path, json.dumps(interview_data, indent=2), None)
    return path


async def scenario(setup: ckit_scenario_setup.ScenarioSetup) -> None:
    await setup.create_group_hire_and_start_bot(
        persona_marketable_name=profprobe_bot.BOT_NAME,
        persona_marketable_version=profprobe_bot.BOT_VERSION_INT,
        persona_setup={
            "use_surveymonkey": False,
            "slack_should_join": "interviews",
            "SLACK_BOT_TOKEN": "test_token",
            "SLACK_APP_TOKEN": "test_app_token"
        },
        inprocess_tools=profprobe_bot.TOOLS,
        bot_main_loop=profprobe_bot.profprobe_main_loop,
        group_prefix="scenario-slack-interview"
    )
    
    pdoc_integration = fi_pdoc.IntegrationPdoc(setup.fclient, setup.fgroup_id)
    
    survey_name = "user-experience-interview-2024"
    template_path = await create_interview_template(pdoc_integration, survey_name)
    logger.info(f"Created interview template at {template_path}")
    
    await setup.post_user_message_and_wait_reply(
        f"Start an interview in Slack channel #interviews using the template at {template_path} with respondent John Doe"
    )
    
    await asyncio.sleep(2)
    
    first_question = await wait_for_bot_messages(setup, "interviews")
    assert len(first_question) > 0, "Bot didn't post first question"
    
    await post_fake_slack_message(
        "interviews",
        "I use it mainly for data analysis and reporting",
        user="JohnDoe"
    )
    
    await asyncio.sleep(2)
    
    second_question = await wait_for_bot_messages(setup, "interviews")
    assert len(second_question) > 1, "Bot didn't ask second question"
    
    await post_fake_slack_message(
        "interviews",
        "Daily",
        user="JohnDoe"
    )
    
    await asyncio.sleep(2)
    
    third_question = await wait_for_bot_messages(setup, "interviews")
    assert len(third_question) > 2, "Bot didn't ask third question"
    
    await post_fake_slack_message(
        "interviews",
        "I'd love to see better visualization tools and export options",
        user="JohnDoe"
    )
    
    await asyncio.sleep(2)
    
    results_path = f"/customer-research/unicorn-horn-car-survey-results/{survey_name}-john-doe"
    
    await setup.post_user_message_and_wait_reply(
        f"Save the interview results for John Doe to {results_path}"
    )
    
    await asyncio.sleep(2)
    
    doc = await pdoc_integration.pdoc_cat(results_path)
    content = json.loads(doc.pdoc_content)
    
    assert "John Doe" in str(content), "Respondent name not saved"
    assert len(content.get("responses", content.get("questions", []))) >= 3, "Not all answers saved"
    
    logger.info("✅ Slack interview completed successfully")
    print(f"Interview results saved at: {results_path}")
    
    slack_instance = fake_slack_instances[0]
    all_messages = [msg for msgs in slack_instance.messages.values() for msg in msgs]
    bot_messages = [msg for msg in all_messages if msg.get('user') == 'bot']
    
    assert len(bot_messages) >= 3, f"Expected at least 3 bot messages, got {len(bot_messages)}"
    logger.info(f"Bot asked {len(bot_messages)} questions in total")


if __name__ == "__main__":
    setup = ckit_scenario_setup.ScenarioSetup("profprobe")
    asyncio.run(setup.run_scenario(scenario))
