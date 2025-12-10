from typing import Dict, Any, Optional
from flexus_client_kit import ckit_cloudtool

PRINT_WIDGET_TOOL = ckit_cloudtool.CloudTool(
    name="print_widget",
    description="Print UI widgets for the user to interact with. Common widgets: 'upload-files', 'open-bot-setup-dialog', 'restart-chat'",
    parameters={
        "type": "object",
        "properties": {
            "t": {"type": "string", "description": "Widget type: 'upload-files', 'open-bot-setup-dialog', 'restart-chat'"},
            "q": {"type": "string", "description": "Optional question/message for restart-chat widget"},
        },
        "required": ["t"],
    },
)


async def handle_print_widget(
    toolcall: ckit_cloudtool.FCloudtoolCall,
    model_produced_args: Optional[Dict[str, Any]],
) -> str:
    if not model_produced_args:
        return "Error: widget type 't' required"

    widget_type = model_produced_args.get("t", "")
    question = model_produced_args.get("q", "")

    if not widget_type:
        return "Error: widget type 't' required"

    return f"Printing UI widget: {widget_type}"
