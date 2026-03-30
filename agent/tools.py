"""Tool definitions for the A2A Travel Planner.

Provides both local Pydantic tools and dynamic MCP tool loading.
The Data Fetcher agent uses these to gather live travel data.
"""

import json
import logging
import asyncio
import threading
from typing import Optional

from pydantic import BaseModel, Field
from google.cloud import bigquery

from .config import config

logger = logging.getLogger(__name__)

# ── BigQuery Client (Schema initialization) ───────────────

_bq_client: Optional[bigquery.Client] = None


def _get_bq_client() -> bigquery.Client:
    """Lazy-initialize BigQuery client."""
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=config.google_cloud_project)
    return _bq_client


def get_schema_from_bq() -> str:
    """Retrieve schema for all tables in the source dataset."""
    client = _get_bq_client()
    source = config.bq_source_dataset
    project, dataset = source.split(".")
    schemas = []

    tables = client.list_tables(f"{project}.{dataset}")
    for table_ref in tables:
        table_id = f"{table_ref.project}.{table_ref.dataset_id}.{table_ref.table_id}"
        table_obj = client.get_table(table_id)
        columns = []
        for field in table_obj.schema:
            columns.append({
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description or "",
            })
        schemas.append({
            "table_name": table_id,
            "short_name": table_ref.table_id,
            "num_rows": table_obj.num_rows,
            "columns": columns,
        })

    return json.dumps({"tables": schemas}, indent=2)


# ── Pydantic Tools (local, no MCP) ───────────────────────

class SubmitFinalAnswer(BaseModel):
    """Signals that the agent has completed its task with a final answer."""
    final_answer: str = Field(
        ...,
        description="The natural-language answer to present to the user",
    )


class SubmitFetchedData(BaseModel):
    """Signals that the Data Fetcher has completed data gathering.

    Contains a JSON string with all fetched travel data (places, weather, flights).
    """
    data_summary: str = Field(
        ...,
        description="JSON string containing all fetched travel data: "
                    "{'places': [...], 'weather': {...}, 'flights': [...]}",
    )


# ── MCP Tool Loading ─────────────────────────────────────

def get_tools() -> list:
    """Load tools from the MCP Toolbox Server + local Pydantic tools.

    Returns a list of tools for the Data Fetcher agent to use.
    """
    base_tools = [SubmitFinalAnswer, SubmitFetchedData]

    try:
        from toolbox_core import ToolboxClient
    except ImportError:
        logger.warning("toolbox_core not installed, skipping MCP tools")
        return base_tools

    async def load_mcp_tools():
        async with ToolboxClient(config.mcp_toolbox_uri) as client:
            toolset = await client.load_toolset("travel-agent-tools")
            return toolset

    def fetch_mcp_tools():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(load_mcp_tools())
        finally:
            new_loop.close()

    try:
        mcp_tools = []
        err = None

        def _thread_target():
            nonlocal mcp_tools, err
            try:
                mcp_tools = fetch_mcp_tools()
            except Exception as e:
                err = e

        thread = threading.Thread(target=_thread_target)
        thread.start()
        thread.join()

        if err:
            raise err

        base_tools.extend(mcp_tools)
        logger.info(
            "Loaded %d MCP tools: %s",
            len(mcp_tools),
            [getattr(t, '__name__', getattr(t, 'name', '?')) for t in mcp_tools],
        )

    except Exception as e:
        logger.error(
            "Failed to load MCP tools from %s: %s. Continuing with local tools only.",
            config.mcp_toolbox_uri, e,
        )

    return base_tools
