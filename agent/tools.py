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
from langchain_core.tools import StructuredTool

from .config import config

logger = logging.getLogger(__name__)


def _tool_name(tool_obj) -> str:
    """Return a normalized tool name for BaseTool, ToolboxTool, or callables."""
    return getattr(tool_obj, "name", getattr(tool_obj, "_name", getattr(tool_obj, "__name__", "")))

# ── BigQuery Client (Schema initialization) ───────────────

_bq_client: Optional[bigquery.Client] = None
_cached_tools: Optional[list] = None


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


def _run_async_callable_in_thread(async_callable, **kwargs):
    """Run an async callable from sync code without reusing the caller's loop."""
    result = None
    error = None

    def _target():
        nonlocal result, error
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_callable(**kwargs))
        except Exception as exc:  # noqa: BLE001
            error = exc
        finally:
            loop.close()

    thread = threading.Thread(target=_target)
    thread.start()
    thread.join()

    if error:
        raise error
    return result


async def _invoke_mcp_tool_live(tool_name: str, **kwargs):
    """Invoke an MCP tool through a fresh live Toolbox client."""
    from toolbox_core import ToolboxClient
    from toolbox_core.protocol import Protocol

    async with ToolboxClient(
        config.mcp_toolbox_uri,
        protocol=Protocol.MCP_LATEST,
    ) as client:
        live_tool = await client.load_tool(tool_name)
        return await live_tool(**kwargs)


def _wrap_mcp_tool(tool_obj):
    """Adapt Toolbox async tools into LangChain tools with sync + async execution."""
    tool_name = getattr(tool_obj, "_name", getattr(tool_obj, "__name__", "mcp_tool"))
    description = getattr(
        tool_obj,
        "_description",
        getattr(tool_obj, "__doc__", f"{tool_name} MCP tool"),
    )
    args_schema = getattr(tool_obj, "_ToolboxTool__pydantic_model", None)

    async def _ainvoke_mcp_tool(**kwargs):
        return await _invoke_mcp_tool_live(tool_name, **kwargs)

    def _invoke_mcp_tool(**kwargs):
        return _run_async_callable_in_thread(_invoke_mcp_tool_live, tool_name=tool_name, **kwargs)

    _ainvoke_mcp_tool.__name__ = tool_name
    _invoke_mcp_tool.__name__ = tool_name

    return StructuredTool.from_function(
        func=_invoke_mcp_tool,
        coroutine=_ainvoke_mcp_tool,
        name=tool_name,
        description=description,
        args_schema=args_schema,
        infer_schema=args_schema is None,
    )


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
    global _cached_tools
    if _cached_tools is not None:
        return _cached_tools

    base_tools = [SubmitFinalAnswer, SubmitFetchedData]

    try:
        from toolbox_core import ToolboxClient
        from toolbox_core.protocol import Protocol
    except ImportError:
        logger.warning("toolbox_core not installed, skipping MCP tools")
        return base_tools

    async def load_mcp_tools():
        async with ToolboxClient(
            config.mcp_toolbox_uri,
            protocol=Protocol.MCP_LATEST,
        ) as client:
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

        wrapped_tools = [_wrap_mcp_tool(tool) for tool in mcp_tools]
        base_tools.extend(wrapped_tools)
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

    _cached_tools = base_tools
    return _cached_tools


def get_data_fetcher_tools() -> list:
    """Return only the travel-planning tools needed by the Data Fetcher loop."""
    excluded = {"get-schema", "execute-query"}
    return [tool for tool in get_tools() if _tool_name(tool) not in excluded]
