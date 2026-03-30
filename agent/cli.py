"""CLI entrypoint for the A2A Travel Planner — interactive chat mode."""

import uuid
import logging

from rich.console import Console
from rich.markdown import Markdown
from langchain_core.messages import HumanMessage

from .graph import create_agent
from .config import config

console = Console()
logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Run the travel planner in interactive chat mode."""
    console.print(
        "\n[bold cyan]✈️  A2A Travel Planner[/bold cyan] "
        f"| Model: [bold]{config.gemini_model}[/bold]\n"
    )
    console.print(
        "[dim]Multi-agent architecture: Verifier → Orchestrator → Data Fetcher → Planner[/dim]"
    )
    console.print("[dim]Type 'q' to quit.[/dim]\n")

    graph, run_config = create_agent()
    run_config["configurable"]["thread_id"] = str(uuid.uuid4())

    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.strip().lower() in {"q", "quit", "exit"}:
            break

        if not user_input.strip():
            continue

        console.print()
        try:
            for output in graph.stream(
                {
                    "messages": [HumanMessage(content=user_input)],
                },
                config=run_config,
                stream_mode="updates",
            ):
                for node_name, node_output in output.items():
                    messages = node_output.get("messages", [])
                    sender = node_output.get("sender", "System")

                    for msg in messages:
                        content = getattr(msg, "content", "")

                        # Verifier output
                        if sender == "Verifier":
                            if content.startswith("SAFE:"):
                                console.print(f"[bold green]🛡️ Verifier:[/bold green] [dim]{content}[/dim]")
                            elif content.startswith("REJECT:") or content.startswith("BLOCKED"):
                                console.print(f"[bold red]🛡️ Blocked:[/bold red] {content}")

                        # Orchestrator output
                        elif sender == "Orchestrator":
                            if "```json" in content:
                                # Show acknowledgment but not raw JSON
                                text_part = content.split("```json")[0].strip()
                                if text_part:
                                    console.print(f"[bold cyan]🎯 Orchestrator:[/bold cyan] {text_part}")
                                console.print("[dim]  📋 Travel parameters extracted...[/dim]")
                            elif content.startswith("#"):
                                # Final itinerary presentation
                                console.print()
                                console.print(Markdown(content))
                            else:
                                console.print(f"[bold cyan]🎯 Orchestrator:[/bold cyan] {content}")

                        # Data Fetcher output
                        elif sender == "DataFetcher":
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    name = tc.get("name", "")
                                    if name == "search-places":
                                        console.print("  [dim]📍 Searching for places...[/dim]")
                                    elif name == "get-weather":
                                        console.print("  [dim]🌤️ Fetching weather forecast...[/dim]")
                                    elif name == "search-flights":
                                        console.print("  [dim]✈️ Searching flights...[/dim]")
                                    elif name == "get-directions":
                                        console.print("  [dim]🗺️ Getting directions...[/dim]")
                                    elif name == "place-details":
                                        console.print("  [dim]📖 Getting place details...[/dim]")
                                    elif name == "execute-query":
                                        console.print("  [dim]📊 Querying BigQuery...[/dim]")
                                    elif name == "SubmitFetchedData":
                                        console.print("  [dim]✅ Data gathering complete[/dim]")

                        # Planner output
                        elif sender == "Planner":
                            console.print(f"[bold magenta]📋 Planner:[/bold magenta] {content}")

                        # Data processor
                        elif sender == "DataProcessor":
                            places = node_output.get("places_data")
                            weather = node_output.get("weather_data")
                            flights = node_output.get("flight_data")
                            if places:
                                console.print(f"  [green]✓ {len(places)} places found[/green]")
                            if weather:
                                console.print(f"  [green]✓ Weather data received[/green]")
                            if flights:
                                console.print(f"  [green]✓ {len(flights)} flight options[/green]")

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")
            logger.exception("Graph execution error")

        console.print()


if __name__ == "__main__":
    main()
