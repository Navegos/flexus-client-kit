import asyncio
import logging
import json
from typing import Dict, Any

from flexus_client_kit import ckit_client
from flexus_client_kit import ckit_cloudtool
from flexus_client_kit import ckit_bot_exec
from flexus_client_kit import ckit_shutdown
from flexus_client_kit import ckit_ask_model
from flexus_client_kit.integrations import fi_pdoc
from flexus_simple_bots.productman import productman_install
from flexus_simple_bots.version_common import SIMPLE_BOTS_COMMON_VERSION

logger = logging.getLogger("bot_productman")


BOT_NAME = "productman"
BOT_VERSION = SIMPLE_BOTS_COMMON_VERSION
BOT_VERSION_INT = ckit_client.marketplace_version_as_int(BOT_VERSION)


HYPOTHESIS_TEMPLATE_TOOL = ckit_cloudtool.CloudTool(
    name="hypothesis_template",
    description="Create skeleton problem validation form in pdoc. The form tracks validation state from idea through prioritization. Fill fields during conversation - the filled document is the process state.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path where to write template. Should start with /customer-research/ and use kebab-case: '/customer-research/my-saas-tool'"
            },
        },
        "required": ["path"],
    },
)

TOOLS = [
    HYPOTHESIS_TEMPLATE_TOOL,
    fi_pdoc.POLICY_DOCUMENT_TOOL,
]


async def productman_main_loop(fclient: ckit_client.FlexusClient, rcx: ckit_bot_exec.RobotContext) -> None:
    setup = ckit_bot_exec.official_setup_mixing_procedure(productman_install.productman_setup_schema, rcx.persona.persona_setup)

    pdoc_integration = fi_pdoc.IntegrationPdoc(fclient, rcx.persona.located_fgroup_id)

    @rcx.on_updated_message
    async def updated_message_in_db(msg: ckit_ask_model.FThreadMessageOutput):
        pass

    @rcx.on_updated_thread
    async def updated_thread_in_db(th: ckit_ask_model.FThreadOutput):
        pass

    @rcx.on_tool_call(HYPOTHESIS_TEMPLATE_TOOL.name)
    async def toolcall_hypothesis_template(toolcall: ckit_cloudtool.FCloudtoolCall, model_produced_args: Dict[str, Any]) -> str:
        path = model_produced_args.get("path", "")
        if not path:
            return "Error: path required"
        if not path.startswith("/customer-research/"):
            return "Error: path must start with /customer-research/ (e.g. /customer-research/my-product)"
        path_segments = path.strip("/").split("/")
        for segment in path_segments:
            if not segment:
                continue
            if not all(c.islower() or c.isdigit() or c == "-" for c in segment):
                return f"Error: Path segment '{segment}' must use kebab-case (lowercase letters, numbers, hyphens only). Example: 'unicorn-horn-car-attachment'"

        skeleton = {
            "problem_validation": {
                "meta": {
                    "created": "",
                    "status": "in_progress"
                },
                "section01_idea_brief": {
                    "title": "Initial Idea Capture",
                    "field01_title": {"label": "Product idea (3-5 words)", "value": ""},
                    "field02_problem_context": {"label": "What problem does it solve?", "value": ""},
                    "field03_proposed_value": {"label": "What value do you provide?", "value": ""},
                    "field04_constraints": {"label": "Constraints (budget/time/resources)", "value": ""},
                    "field05_audience_hint": {"label": "Target audience", "value": ""}
                },
                "section02_problem_freeform": {
                    "title": "Problem Description",
                    "field01_statement": {"label": "Describe the problem in your own words", "value": ""},
                    "field02_evidence": {"label": "What observations or research support this?", "value": ""},
                    "field03_assumptions": {"label": "What are you assuming?", "value": ""},
                    "field04_risks": {"label": "Known risks", "value": ""}
                },
                "section03_target_audience": {
                    "title": "Audience Profile",
                    "field01_segments": {"label": "Audience segments (roles, industries, sizes)", "value": ""},
                    "field02_jobs_to_be_done": {"label": "What tasks are they trying to accomplish?", "value": ""},
                    "field03_pains": {"label": "What frustrates them?", "value": ""},
                    "field04_gains": {"label": "What outcomes do they want?", "value": ""},
                    "field05_channels": {"label": "Where do they hang out?", "value": ""},
                    "field06_geography": {"label": "Geographic locations", "value": ""},
                    "field07_languages": {"label": "Languages spoken", "value": ""}
                },
                "section04_guess_the_business": {
                    "title": "Hypothesis Challenge Game (iterate until unique)",
                    "rounds": []
                },
                "section05_hypotheses_list": {
                    "title": "Structured Problem Hypotheses (3-10)",
                    "hypotheses": []
                },
                "section06_prioritization_criteria": {
                    "title": "Scoring Dimensions Setup",
                    "field01_impact": {"weight": 0.3, "scale": "1-5", "definition": ""},
                    "field02_evidence": {"weight": 0.3, "scale": "1-5", "definition": ""},
                    "field03_urgency": {"weight": 0.2, "scale": "1-5", "definition": ""},
                    "field04_feasibility": {"weight": 0.2, "scale": "1-5", "definition": ""}
                },
                "section07_market_sources": {
                    "title": "Personalized Research Sources",
                    "preferences": {
                        "domains": "",
                        "geographies": "",
                        "languages": "",
                        "paid_allowed": False,
                        "data_freshness": ""
                    },
                    "sources": []
                },
                "section08_prioritized_hypotheses": {
                    "title": "Scored & Ranked Hypotheses",
                    "results": []
                }
            }
        }

        await pdoc_integration.pdoc_write(path, json.dumps(skeleton, indent=2), toolcall.fcall_ft_id)
        logger.info(f"Created validation template at {path}")
        return f"✍🏻 {path}\n\n✓ Created problem validation template"

    @rcx.on_tool_call(fi_pdoc.POLICY_DOCUMENT_TOOL.name)
    async def toolcall_pdoc(toolcall: ckit_cloudtool.FCloudtoolCall, model_produced_args: Dict[str, Any]) -> str:
        return await pdoc_integration.called_by_model(toolcall, model_produced_args)

    try:
        while not ckit_shutdown.shutdown_event.is_set():
            await rcx.unpark_collected_events(sleep_if_no_work=10.0)

    finally:
        logger.info("%s exit" % (rcx.persona.persona_id,))


def main():
    group = ckit_bot_exec.parse_bot_group_argument()
    fclient = ckit_client.FlexusClient(ckit_client.bot_service_name(BOT_NAME, BOT_VERSION_INT, group), endpoint="/v1/jailed-bot")

    asyncio.run(ckit_bot_exec.run_bots_in_this_group(
        fclient,
        marketable_name=BOT_NAME,
        marketable_version=BOT_VERSION_INT,
        fgroup_id=group,
        bot_main_loop=productman_main_loop,
        inprocess_tools=TOOLS,
    ))


if __name__ == "__main__":
    main()
