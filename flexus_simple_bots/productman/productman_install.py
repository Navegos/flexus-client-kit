import asyncio
import json
import base64
from pathlib import Path

from flexus_client_kit import ckit_client
from flexus_client_kit import ckit_bot_install

from flexus_simple_bots.productman import productman_bot, productman_prompts


BOT_DESCRIPTION = """
## ProductMan - Hypothesis-Driven Product Manager

A systematic product manager that helps you formulate, test, and iterate on product hypotheses using structured thinking.

**Hypothesis Formula:**
"My client wants to [DO SOMETHING] but currently cannot because [BLOCKER]. To test it I need [TEST METHOD] and success would be [SUCCESS CRITERIA]."

**Key Features:**
- **Structured Hypothesis Creation**: Guides you through formulating testable product hypotheses
- **Variation Generation**: Creates multiple angles to test each hypothesis
- **Policy Documents**: Maintains .pdoc files for all hypotheses, interviews, and experiments
- **Weekly Reviews**: Automatically surfaces hypotheses to revisit and test
- **Customer Research**: Documents customer interviews in structured format
- **Experiment Tracking**: Tracks test results and learnings

**Perfect for:**
- Product managers defining new features
- Startups validating product-market fit
- Teams practicing hypothesis-driven development
- Research and customer discovery

ProductMan keeps your product thinking organized and testable, turning ideas into actionable experiments.
"""


productman_setup_schema = [
    {
        "bs_name": "weekly_review_day",
        "bs_type": "string_short",
        "bs_default": "Monday",
        "bs_group": "Schedule",
        "bs_order": 1,
        "bs_importance": 0,
        "bs_description": "Which day of the week to review hypotheses (Monday, Tuesday, etc.)",
    },
    {
        "bs_name": "auto_generate_variations",
        "bs_type": "bool",
        "bs_default": True,
        "bs_group": "Behavior",
        "bs_order": 1,
        "bs_importance": 0,
        "bs_description": "Automatically generate hypothesis variations after creating original",
    },
    {
        "bs_name": "num_variations_default",
        "bs_type": "int",
        "bs_default": 3,
        "bs_group": "Behavior",
        "bs_order": 2,
        "bs_importance": 0,
        "bs_description": "Default number of variations to generate (1-5)",
    },
]


PRODUCTMAN_SUBCHAT_LARK = f"""
print("Generating hypothesis variation in subchat")
subchat_result = "Variation generated"
"""

PRODUCTMAN_DEFAULT_LARK = f"""
print("Processing %d messages" % len(messages))
msg = messages[-1]
if msg["role"] == "assistant":
    assistant_text = str(msg.get("content", ""))
    if "hypothesis" in assistant_text.lower():
        print("Hypothesis discussion detected")
"""


async def install(
    client: ckit_client.FlexusClient,
    ws_id: str,
):
    bot_internal_tools = json.dumps([t.openai_style_tool() for t in productman_bot.TOOLS])
    pic_big = base64.b64encode(open(Path(__file__).with_name("productman-1024x1536.webp"), "rb").read()).decode("ascii")
    pic_small = base64.b64encode(open(Path(__file__).with_name("productman-256x256.webp"), "rb").read()).decode("ascii")
    await ckit_bot_install.marketplace_upsert_dev_bot(
        client,
        ws_id=ws_id,
        marketable_name=productman_bot.BOT_NAME,
        marketable_version=productman_bot.BOT_VERSION,
        marketable_accent_color="#4A90E2",
        marketable_title1="ProductMan",
        marketable_title2="Your hypothesis-driven product manager. Formulate, test, and iterate on product ideas systematically.",
        marketable_author="Flexus",
        marketable_occupation="Product Manager",
        marketable_description=BOT_DESCRIPTION,
        marketable_typical_group="Product / Research",
        marketable_github_repo="https://github.com/smallcloudai/flexus-client-kit.git",
        marketable_run_this="python -m flexus_simple_bots.productman.productman_bot",
        marketable_setup_default=productman_setup_schema,
        marketable_featured_actions=[
            {"feat_question": "Help me create a new product hypothesis", "feat_run_as_setup": False, "feat_depends_on_setup": []},
            {"feat_question": "Review my existing hypotheses", "feat_run_as_setup": False, "feat_depends_on_setup": []},
            {"feat_question": "Document a customer interview", "feat_run_as_setup": False, "feat_depends_on_setup": []},
        ],
        marketable_intro_message="Hi! I'm ProductMan, your hypothesis-driven product manager. I help you formulate testable product hypotheses using the formula: 'My client wants to [DO] but currently cannot because [BLOCKER]. To test it I need [TEST] and success would be [SUCCESS].' Ready to explore a product idea?",
        marketable_preferred_model_default="grok-code-fast-1",
        marketable_daily_budget_default=200_000,
        marketable_default_inbox_default=20_000,
        marketable_expert_default=ckit_bot_install.FMarketplaceExpertInput(
            fexp_name="productman_default",
            fexp_system_prompt=productman_prompts.short_prompt,
            fexp_python_kernel=PRODUCTMAN_DEFAULT_LARK,
            fexp_block_tools="*setup*",
            fexp_allow_tools="",
            fexp_app_capture_tools=bot_internal_tools,
        ),
        marketable_expert_setup=ckit_bot_install.FMarketplaceExpertInput(
            fexp_name="productman_setup",
            fexp_system_prompt=productman_prompts.productman_setup,
            fexp_python_kernel=PRODUCTMAN_DEFAULT_LARK,
            fexp_block_tools="",
            fexp_allow_tools="",
            fexp_app_capture_tools=bot_internal_tools,
        ),
        marketable_expert_subchat=ckit_bot_install.FMarketplaceExpertInput(
            fexp_name="productman_subchat",
            fexp_system_prompt=productman_prompts.short_prompt,
            fexp_python_kernel=PRODUCTMAN_SUBCHAT_LARK,
            fexp_block_tools="*setup*,generate_hypothesis_variations",
            fexp_allow_tools="",
            fexp_app_capture_tools=bot_internal_tools,
        ),
        marketable_tags=["Product Management", "Research", "Hypothesis Testing"],
        marketable_picture_big_b64=pic_big,
        marketable_picture_small_b64=pic_small,
        marketable_schedule=[
            {
                "sched_type": "SCHED_TASK_SORT",
                "sched_when": "EVERY:10m",
                "sched_first_question": "Look at inbox tasks and prioritize hypotheses that need attention. Sort them by urgency and potential impact.",
            },
            {
                "sched_type": "SCHED_TODO",
                "sched_when": "EVERY:5m",
                "sched_first_question": "Work on the assigned hypothesis task. Guide the user through the hypothesis formula or generate variations as needed.",
            },
        ]
    )


if __name__ == "__main__":
    args = ckit_bot_install.bot_install_argparse()
    client = ckit_client.FlexusClient("productman_install")
    asyncio.run(install(client, ws_id=args.ws))
