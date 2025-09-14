import asyncio
import logging
import time
from typing import Dict, Any, Optional
from pymongo.collection import Collection

from flexus_client_kit import ckit_cloudtool, ckit_mongo

logger = logging.getLogger("fi_postgres")


POSTGRES_TOOL = ckit_cloudtool.CloudTool(
    name="postgres",
    description="Execute PostgreSQL queries via psql command line utility",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "SQL query to execute, if there's data then it's on your to escape it according to SQL rules. This does not go via shell so no shell escape necessary."
            }
        },
        "required": ["query"]
    },
)


class IntegrationPostgres:
    def __init__(self, personal_mongo: Optional[Collection] = None, save_to_mongodb_threshold_bytes: int = 100):
        self.personal_mongo = personal_mongo
        self.save_to_mongodb_threshold_bytes = save_to_mongodb_threshold_bytes

    async def execute_query(self, query: str) -> str:
        try:
            cmd = ["psql", "--csv", "-c", query]
            logger.info("Running %s", query[:30])   # Maybe there is user data so we cut it short

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace').strip()
                return f"{error_msg}"

            result = stdout.decode('utf-8', errors='replace').strip()
            if not result:
                return "Query executed successfully"

            result_bytes = result.encode('utf-8')
            lines = result.split('\n')
            row_count = len(lines) - 1

            if len(result_bytes) > self.save_to_mongodb_threshold_bytes and self.personal_mongo is not None and len(lines) > 7:
                timestamp = str(int(time.time()))
                file_path = f"postgres/query_{timestamp}.csv"
                await ckit_mongo.store_file(self.personal_mongo, file_path, result_bytes)

                header_and_first_3 = '\n'.join(lines[:4])
                last_3 = '\n'.join(lines[-3:])

                preview = header_and_first_3 +  "\n...\n" + last_3

                explanation  = "Query executed successfully, in the preview below the first line is CSV headers, then first 3 lines, dot dot dot, and last 3 lines of data. There are %d lines of data total.\n" % (row_count,)
                explanation += "Full CSV is accessible via mongo_store() tool using path: %s\n\n" % (file_path,)
                return explanation + preview

            explanation = "Query executed successfully, first line is CSV headers, then %d lines of data, %d lines total:\n\n" % (row_count, row_count+1)
            return explanation + result

        except FileNotFoundError:
            return "Error: this integration relies on psql command line utility and it doesn't work"

        except Exception:
            logger.exception("Unexpected problem")
            return "Internal error, more information in the bot logs :/"

    async def called_by_model(
        self,
        toolcall: ckit_cloudtool.FCloudtoolCall,
        model_produced_args: Dict[str, Any],
    ) -> str:
        query = model_produced_args.get("query")
        if not query:
            return "Error: specify `query` parameter"
        return await self.execute_query(query)


if __name__ == "__main__":
    async def test():
        postgres = IntegrationPostgres()
        result = await postgres.execute_query("SELECT 2*2;")
        print("Test result:", result)
    asyncio.run(test())
