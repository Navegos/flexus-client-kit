import json
import logging

from datetime import datetime
from typing import Dict, Any, Optional
from pymongo.collection import Collection
from zoneinfo import ZoneInfo

from flexus_client_kit import ckit_cloudtool, ckit_mongo
from flexus_client_kit.integrations.report_utils import generate_pdf

logger = logging.getLogger("reprt")


REPORT_TOOL = ckit_cloudtool.CloudTool(
    name="report",
    description="Daily/weekly reporting tool - append text/images to sections, export PDF. "
                "Start with op=help. Call with p=daily, p=weekly, ... for the current status.",
    parameters={
        "type": "object",
        "properties": {
            "p": {"type": "string", "description": "Name of a report: 'daily', 'weekly' or a custom name"},
            "op": {"type": "string", "description": "Operation: append/overwrite/export_pdf"},
            "section": {"type": "string", "description": "Section name to update (e.g., 'frontpage', 'todo', ...)"},
            "text": {"type": "string", "description": "Text content to add to section"},
        },
        "required": ["p"],
    },
)

HELP = """
Usage:

report(p="daily/weekly/<custom_name>")
    Print current status.

report(p="daily", op="append", section="20250303-widgets-in-our-company", text="...text...")
    Append text to a section. Creates section if it doesn't exist. Instead of "append" you can
    also use "overwrite". The format is markdown, you can use headers, *italic*, horizontal line, etc.

report(p="daily", op="append", section="todo", text="<section_name_1>,<section_name_2>")
    The "todo" section is a meta column, it won't appear in PDF but is useful to track the progress.
    Put section names as comma-separated list.

report(p="daily", op="append", section="frontpage", text="...text...")
    The "frontpage" section is special! It appears first in final PDF.

report(p="daily", op="export_pdf")
    Export current report to PDF, saves as daily-YYYYMMDD.pdf to mongodb.
"""



async def handle_report(
    ws_timezone: str,
    mongo_collection: Collection,
    model_produced_args: Optional[Dict[str, Any]],
) -> str:
    if not model_produced_args or not model_produced_args.get("p"):
        return HELP

    p = model_produced_args.get("p", "")
    op = model_produced_args.get("op", "")
    section = model_produced_args.get("section", "")
    text = model_produced_args.get("text", "")

    result = []
    tz = ZoneInfo(ws_timezone)
    timekey = datetime.now(tz).strftime("%Y%m%d")
    report_path = "%s-%s-report.json" % (timekey, p)
    pdf_path = "%s-%s-report.pdf" % (timekey, p)
    result.append("It's %s in %s" % (datetime.now(tz).strftime("%Y%m%d %H:%M:%S"), ws_timezone))

    report_doc = await ckit_mongo.retrieve_file(mongo_collection, report_path)
    if report_doc:
        report_data = report_doc["json"]
    else:
        report_data = {}
    todo = report_data.setdefault("todo", [])
    frontpage = report_data.setdefault("frontpage", [])
    sections = report_data.setdefault("sections", {})

    if not op:
        result.append("Report draft that will eventually become %s:" % pdf_path)
        result.append("")
        result.append(json.dumps(report_data, indent=2))
        result.append(HELP)

    elif op in ["append", "overwrite"]:
        if not section:
            return "Error: section parameter required"
        if not text:
            return "Error: text parameter required"
        if section == "frontpage":
            target = frontpage
        elif section == "todo":
            target = todo
        else:
            target = sections.setdefault(section, [])

        if section != "todo":
            todo = [s for s in todo if s != section]
            if op == "overwrite":
                target.clear()
            if text:
                target.append({"m_type": "text", "m_content": text})
            error = test_section_works_in_pdf(section, target)
            if error:
                return f"Section updated but PDF test failed, you need to use op=overwrite to retry, error was: {error}"
        else:
            target += text.split(",") + ["frontpage"]

        report_data["todo"] = list(set(todo))
        todo_msg = "todo:\n%s" % "\n".join(todo)
        todo_msg += "\nYou may need to call kanban_restart() to start filling up the next section"
        await ckit_mongo.store_file(mongo_collection, report_path, json.dumps(report_data).encode('utf-8'))
        return "Updated section '%s' in %s\n%s" % (section, report_path, todo_msg)

    elif op == "export_pdf":
        del report_data["todo"]
        pdf_bytes = generate_pdf(report_data)
        await ckit_mongo.store_file(mongo_collection, pdf_path, pdf_bytes)
        result.append("Exported report to %s in MongoDB" % pdf_path)

    else:
        return "Error: need a valid `op` parameter, here is help\n" + HELP

    return "\n".join(result)


def test_section_works_in_pdf(section_name: str, section_items: list) -> Optional[str]:
    """Test a single section to catch PDF generation errors early."""
    try:
        if section_name == "frontpage":
            test_data = {"frontpage": section_items}
        else:
            test_data = {"sections": {section_name: section_items}}
        _ = generate_pdf(test_data)
        return None
    except Exception as e:
        error_msg = f"Error in section '{section_name}': {e}"
        logger.error(error_msg)
        return error_msg
