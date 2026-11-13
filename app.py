#!/usr/bin/env python3
"""
app.py — Interactive CLI chatbot interface for the Nosh Robotics Recipe Assistant.

Usage:
    python app.py

Commands during chat:
    /reset  — Clear all active session filters and start fresh
    /state  — Show current session state (active filters, last shown recipes)
    /exit   — Quit the chatbot
    /help   — Show available commands
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text
from rich import print as rprint

from src.agent import create_agent

load_dotenv()

console = Console()

WELCOME_TEXT = """
# 🍳 Nosh Robotics Recipe Assistant

Powered by **Gemini 3.8 Flash** + **SQLite FTS5** — all recipe facts are grounded in data.

**What I can do:**
- 🔍 Search recipes by name, ingredients, or cuisine
- 📊 Compute exact dataset statistics (counts, rankings, common ingredients)
- 🛒 Match recipes to your pantry ingredients with explainable scoring
- 🔄 Suggest evidence-backed ingredient substitutions

**Commands:** `/reset` · `/state` · `/help` · `/exit`
"""

HELP_TEXT = """
**Available Commands:**
- `/reset` — Clear all active filters and session state
- `/state` — Show current active filters (exclusions, pantry, max steps)
- `/help`  — Show this help message
- `/exit`  — Quit the chatbot

**Example Questions:**
- "Find a penne pasta recipe"
- "I cannot have dairy" *(refines previous search)*
- "How many recipes contain both garlic and onion? What percentage?"
- "Among tomato recipes, which 5 have the fewest instruction steps?"
- "I have eggs, onions, tomatoes, and rice — suggest 5 recipes, no peanuts, at most 6 steps"
- "Take this banana bread recipe and remove eggs — what replacements have dataset evidence?"
"""


def print_welcome():
    console.print(Markdown(WELCOME_TEXT))
    console.print(Rule(style="dim"))


def print_response(text: str):
    """Print the agent's markdown response in a styled panel."""
    try:
        md = Markdown(text)
        console.print(Panel(md, border_style="green", padding=(1, 2)))
    except Exception:
        console.print(Panel(text, border_style="green", padding=(1, 2)))


def print_state(agent):
    """Display current session state."""
    state = agent.state
    lines = [
        f"[bold]Active Filters:[/bold]",
        f"  Last query: {state.last_query or '(none)'}",
        f"  Pantry ingredients: {state.pantry_ingredients or '(none)'}",
        f"  Include ingredients: {state.include_ingredients or '(none)'}",
        f"  Exclude ingredients: {state.exclude_ingredients or '(none)'}",
        f"  Max steps: {state.max_steps or '(none)'}",
        f"  Active recipe ID: {state.active_recipe_id or '(none)'}",
        f"  Last shown IDs: {state.last_shown_recipe_ids[:5] or '(none)'}",
    ]
    console.print(Panel("\n".join(lines), title="[bold cyan]Session State[/bold cyan]", border_style="cyan"))


def check_db_exists() -> bool:
    """Check that the database has been built."""
    db_path = Path("data/recipes.db")
    if not db_path.exists():
        console.print(Panel(
            "[bold red]Database not found![/bold red]\n\n"
            "Please run [bold cyan]python src/ingest.py[/bold cyan] first to build the recipe database.\n\n"
            "Quick test (100 recipes per source):\n"
            "[bold cyan]python src/ingest.py --limit 100[/bold cyan]",
            title="Setup Required",
            border_style="red",
        ))
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Nosh Robotics Recipe Assistant")
    parser.add_argument("--web", action="store_true", help="Launch interactive browser Web UI instead of CLI")
    parser.add_argument("--port", type=int, default=8000, help="Port for Web UI (default: 8000)")
    args = parser.parse_args()

    if args.web:
        if not check_db_exists():
            sys.exit(1)
        from web_app import run_web
        run_web(port=args.port)
        return

    print_welcome()

    if not check_db_exists():
        sys.exit(1)

    console.print("[dim]Initializing agent...[/dim]")
    try:
        agent = create_agent()
        console.print("[green]✓ Agent ready.[/green]\n")
    except ValueError as e:
        console.print(Panel(
            f"[bold red]Error:[/bold red] {e}\n\n"
            "Make sure you have copied [cyan].env.example[/cyan] to [cyan].env[/cyan] "
            "and set your [cyan]GEMINI_API_KEY[/cyan].",
            border_style="red",
        ))
        sys.exit(1)

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Handle slash commands
        cmd = user_input.lower()

        if cmd in ("/exit", "/quit", "exit", "quit"):
            console.print("[dim]Goodbye![/dim]")
            break

        elif cmd == "/reset":
            agent.reset()
            console.print("[yellow]✓ Session state cleared. Starting fresh.[/yellow]")
            continue

        elif cmd == "/state":
            print_state(agent)
            continue

        elif cmd in ("/help", "/?"):
            console.print(Markdown(HELP_TEXT))
            continue

        # Normal chat turn
        console.print(Rule(style="dim"))
        with console.status("[dim]Thinking...[/dim]", spinner="dots"):
            try:
                response = agent.chat(user_input)
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                continue

        console.print("[bold green]Assistant[/bold green]")
        print_response(response)


if __name__ == "__main__":
    main()
