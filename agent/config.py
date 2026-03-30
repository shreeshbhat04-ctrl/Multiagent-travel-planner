"""Agent configuration module — loads settings from .env file."""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    """Configuration for the A2A Travel Planner Agent."""

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env"),
        case_sensitive=False,
        extra="ignore",
    )

    # ── Google Cloud ──────────────────────────────────────
    google_cloud_project: str = Field(
        default="your-project-id",
        description="GCP Project ID",
    )
    google_cloud_location: str = Field(
        default="US",
        description="BigQuery dataset location",
    )
    google_cloud_region: str = Field(
        default="us-central1",
        description="Region for Vertex AI endpoints",
    )
    google_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API Key",
    )

    # ── Google Maps ───────────────────────────────────────
    google_maps_api_key: Optional[str] = Field(
        default=None,
        description="Google Maps Platform API Key (Places, Routes, Directions)",
    )

    # ── Weather ───────────────────────────────────────────
    openweathermap_api_key: Optional[str] = Field(
        default=None,
        description="OpenWeatherMap API Key (free tier)",
    )
    aviationstack_api_key: Optional[str] = Field(
        default=None,
        description="AviationStack API Key for flight lookups",
    )
    serpapi_api_key: Optional[str] = Field(
        default=None,
        description="SerpApi key for Google Flights results",
    )
    aviationstack_api_key: Optional[str] = Field(
        default=None,
        description="AviationStack API Key for flight status/search",
    )

    # ── BigQuery ──────────────────────────────────────────
    bq_source_dataset: str = Field(
        default="bigquery-public-data.thelook_ecommerce",
        description="Source dataset to query",
    )

    # ── Agent Models ─────────────────────────────────────
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Primary Gemini model for orchestrator and data fetcher",
    )
    planner_model: str = Field(
        default="gemini-2.5-flash",
        description="Model for the planner agent (benefits from strong reasoning)",
    )

    # ── MCP Toolbox ───────────────────────────────────────
    use_mcp_toolbox: bool = Field(
        default=True,
        description="Use MCP Toolbox for Databases",
    )
    mcp_toolbox_uri: str = Field(
        default="http://127.0.0.1:5000",
        description="URI of the MCP Toolbox server",
    )

    # ── Guardrails ────────────────────────────────────────
    max_bytes_processed: int = Field(
        default=2_147_483_648,  # 2 GB
        description="Max bytes scanned per query (dry-run cap)",
    )
    max_recursion_limit: int = Field(
        default=30,
        description="Max LangGraph recursion depth",
    )


# Singleton config instance
config = AgentConfig()
