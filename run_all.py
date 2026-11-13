#!/usr/bin/env python3
"""
run_all.py — Single-command end-to-end runner for all tasks in the Nosh Robotics Assignment.

Demonstrates all required tasks in sequence:
  - Task 1: Recipe Search, Multi-turn Dietary Follow-up & Factual Dataset Statistics
  - Task 2: Ingredient-Based Pantry Matching, Explainable Scoring & Constraint Enforcement
  - Task 3: Local Dataset Substitution Evidence Mining & Recipe Adaptation
  - Task 4: Grounded Architecture vs. Naive LLM Hallucination Benchmark

Usage:
    python run_all.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

load_dotenv()
console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "recipes.db"


def print_header():
    console.print()
    console.print(
        Panel(
            "[bold white]🍳 NOSH ROBOTICS — GENAI INTERN ASSIGNMENT[/bold white]\n"
            "[dim]Complete End-to-End Demonstration across Tasks 1, 2, and 3[/dim]\n\n"
            "[bold green]✓ Dataset:[/bold green] Eight Portions Recipe Box (124,483 recipes in local SQLite FTS5)\n"
            "[bold green]✓ Architecture:[/bold green] Deterministic Tool-Calling (LLM never guesses counts, rankings, or content)\n"
            "[bold green]✓ LLM Engine:[/bold green] Google Gemini (google-genai SDK)",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()


def check_prerequisites():
    if not DB_PATH.exists():
        console.print(
            Panel(
                "[bold red]Database not found![/bold red]\n"
                f"Missing {DB_PATH}.\n\n"
                "Please run ingestion first:\n"
                "  [bold cyan]python src/ingest.py[/bold cyan] (or [bold cyan]python src/ingest.py --limit 100[/bold cyan])",
                border_style="red",
            )
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# TASK 1: Recipe Search & Factual Q&A
# ---------------------------------------------------------------------------
def run_task_1():
    console.print(Rule("[bold cyan]TASK 1: Recipe Search & Factual Q&A (Score: 3/10)[/bold cyan]", style="cyan"))
    from src.tools import compute_dataset_stats, search_recipes

    # 1A: Search recipes
    console.print("\n[bold yellow]1A. Recipe Search: 'penne pasta'[/bold yellow]")
    s_res = search_recipes(query="penne pasta", limit=3)
    t_search = Table(title="Search Results: 'penne pasta'", border_style="dim", header_style="bold green")
    t_search.add_column("Recipe ID", style="cyan", width=22)
    t_search.add_column("Title", style="bold white", width=38)
    t_search.add_column("Steps", justify="right", width=8)
    t_search.add_column("Key Ingredients Sample", style="dim", width=40)
    for r in s_res["results"]:
        sample_ings = ", ".join(r["ingredients_raw"][:3]) + ("..." if len(r["ingredients_raw"]) > 3 else "")
        t_search.add_row(r["recipe_id"], r["title"], str(r["step_count"]), sample_ings)
    console.print(t_search)

    # 1B: Search with hard exclusion
    console.print("\n[bold yellow]1B. Dietary Restriction Filter: 'penne pasta' without dairy[/bold yellow]")
    s_dairy = search_recipes(query="penne pasta", exclude_ingredients=["dairy"], limit=3)
    t_dairy = Table(title="Dairy-Free Penne Results", border_style="dim", header_style="bold green")
    t_dairy.add_column("Recipe ID", style="cyan", width=22)
    t_dairy.add_column("Title", style="bold white", width=38)
    t_dairy.add_column("Steps", justify="right", width=8)
    t_dairy.add_column("Verified Ingredients", style="green", width=40)
    for r in s_dairy["results"]:
        t_dairy.add_row(r["recipe_id"], r["title"], str(r["step_count"]), ", ".join(r["ingredients_raw"][:3]))
    console.print(t_dairy)
    console.print(f"[dim]Expanded dairy exclusions applied in SQL: {len(s_dairy['filters_applied']['expanded_exclusions'])} normalized items.[/dim]")

    # 1C: Aggregate Statistics
    console.print("\n[bold yellow]1C. Factual Analytical Query: Recipes containing both Garlic & Onion[/bold yellow]")
    stats = compute_dataset_stats(stat_type="count", include_ingredients=["garlic", "onion"], group_by="source")
    p_stats = Panel(
        f"[bold]Numerator (Garlic + Onion):[/bold] [green]{stats['numerator']:,}[/green] recipes\n"
        f"[bold]Denominator (Total Dataset):[/bold] [cyan]{stats['denominator']:,}[/cyan] recipes\n"
        f"[bold]Exact Percentage:[/bold] [bold yellow]{stats['percentage']}%[/bold yellow]\n\n"
        f"[bold]Normalization Note:[/bold] {stats['normalization_note']}\n"
        f"[bold]Source Breakdown:[/bold] " + ", ".join(f"{b['source'].upper()}: {b['count']:,}" for b in stats.get("breakdown_by_source", [])),
        title="[bold green]Exact Reproducible Dataset Statistics[/bold green]",
        border_style="green",
    )
    console.print(p_stats)

    # 1D: Fewest Steps Ranking
    console.print("\n[bold yellow]1D. Step-Count Ranking: Top 5 Tomato Recipes with Fewest Steps[/bold yellow]")
    fewest = compute_dataset_stats(stat_type="fewest_steps", include_ingredients=["tomato"], top_n=5)
    t_steps = Table(title="Tomato Recipes Ranked by Fewest Instruction Steps", border_style="dim", header_style="bold green")
    t_steps.add_column("Rank", justify="center", width=6)
    t_steps.add_column("Recipe ID", style="cyan", width=22)
    t_steps.add_column("Title", style="bold white", width=35)
    t_steps.add_column("Steps", justify="center", width=8)
    t_steps.add_column("Instruction Snippet", style="dim", width=42)
    for row in fewest["results"]:
        snippet = row["instructions_snippet"].replace("\n", " ").strip()[:60] + "..."
        t_steps.add_row(str(row["rank"]), row["recipe_id"], row["title"], str(row["step_count"]), snippet)
    console.print(t_steps)
    console.print(f"[dim]Step counting rule: {fewest['step_counting_rule']}[/dim]\n")


# ---------------------------------------------------------------------------
# TASK 2: Ingredient-Based Recipe Matching
# ---------------------------------------------------------------------------
def run_task_2():
    console.print(Rule("[bold cyan]TASK 2: Ingredient-Based Recipe Matching (Score: 3/10)[/bold cyan]", style="cyan"))
    from src.tools import match_pantry_recipes

    # 2A: Pantry Matching
    pantry = ["eggs", "onions", "tomatoes", "rice"]
    console.print(f"\n[bold yellow]2A. Pantry Match: {pantry} | Exclude: peanuts | Max steps: 6[/bold yellow]")
    m1 = match_pantry_recipes(
        available_ingredients=pantry,
        exclude_ingredients=["peanuts"],
        max_steps=6,
        limit=5,
    )
    t_pantry = Table(title="Ranked Eligible Recipes (Scoring: +2.0*matched - 1.0*extra - 0.15*steps)", border_style="dim", header_style="bold green")
    t_pantry.add_column("Recipe ID", style="cyan", width=22)
    t_pantry.add_column("Title", style="bold white", width=30)
    t_pantry.add_column("Score", justify="right", style="bold yellow", width=8)
    t_pantry.add_column("Matched", style="green", width=22)
    t_pantry.add_column("Extra Needed", style="dim", width=28)
    t_pantry.add_column("Steps", justify="center", width=7)
    for r in m1["eligible_recipes"]:
        extra_txt = ", ".join(r["missing_from_pantry"][:4]) + ("..." if len(r["missing_from_pantry"]) > 4 else "")
        t_pantry.add_row(
            r["recipe_id"],
            r["title"][:28],
            str(r["score"]),
            ", ".join(r["matched_ingredients"]),
            extra_txt,
            str(r["step_count"]),
        )
    console.print(t_pantry)
    console.print(f"[dim]Total eligible recipes before ranking: {m1['total_eligible_before_ranking']} | {m1['quantity_verification']}[/dim]")

    # 2B: Follow-up Re-ranking
    console.print("\n[bold yellow]2B. Multi-turn Follow-up: 'Exclude eggs too'[/bold yellow]")
    m2 = match_pantry_recipes(
        available_ingredients=pantry,
        exclude_ingredients=["peanuts", "eggs"],
        max_steps=6,
        limit=5,
    )
    t_no_eggs = Table(title="Updated Rankings with Eggs Excluded", border_style="dim", header_style="bold green")
    t_no_eggs.add_column("Recipe ID", style="cyan", width=22)
    t_no_eggs.add_column("Title", style="bold white", width=30)
    t_no_eggs.add_column("Score", justify="right", style="bold yellow", width=8)
    t_no_eggs.add_column("Matched", style="green", width=22)
    t_no_eggs.add_column("Steps", justify="center", width=7)
    for r in m2["eligible_recipes"]:
        t_no_eggs.add_row(r["recipe_id"], r["title"][:28], str(r["score"]), ", ".join(r["matched_ingredients"]), str(r["step_count"]))
    console.print(t_no_eggs)
    console.print(f"[dim]Eligible count updated: {m1['total_eligible_before_ranking']} -> {m2['total_eligible_before_ranking']} (egg recipes removed).[/dim]")

    # 2C: Contradictory Constraint No-Match Edge Case
    console.print("\n[bold yellow]2C. No-Match Edge Case: Contradictory Constraints (Never Silently Relaxed)[/bold yellow]")
    m_none = match_pantry_recipes(
        available_ingredients=["egg", "butter", "milk"],
        exclude_ingredients=["dairy", "eggs"],
        max_steps=1,
        limit=5,
    )
    p_none = Panel(
        f"[bold red]Eligible Recipes Count:[/bold red] {len(m_none['eligible_recipes'])}\n"
        f"[bold]Reason:[/bold] {m_none.get('no_match_reason')}\n\n"
        f"[bold yellow]Closest Violating Alternatives (Separately Flagged):[/bold yellow]\n"
        + "\n".join(
            f"  - [bold]{alt['title']}[/bold] (ID: {alt['recipe_id']}) -> Violated: {alt['violated_constraints']}"
            for alt in m_none.get("closest_violating_alternatives", [])[:2]
        ),
        title="[bold red]Strict Hard-Constraint Enforcement Verification[/bold red]",
        border_style="red",
    )
    console.print(p_none)
    console.print()


# ---------------------------------------------------------------------------
# TASK 3: Evidence-Based Ingredient Substitution
# ---------------------------------------------------------------------------
def run_task_3():
    console.print(Rule("[bold cyan]TASK 3: Evidence-Based Ingredient Substitution (Score: 4/10)[/bold cyan]", style="cyan"))
    from src.tools import find_substitution_evidence

    # 3A: Banana Bread without eggs
    console.print("\n[bold yellow]3A. Adapt Banana Bread: Remove Eggs (Restrictions: No Dairy)[/bold yellow]")
    sub1 = find_substitution_evidence(
        recipe_id_or_title="banana bread",
        target_ingredient="egg",
        restrictions=["dairy"],
    )
    t_sub1 = Table(title=f"Substitutes Mined for '{sub1['target_recipe']['title']}' (ID: {sub1['target_recipe']['recipe_id']})", border_style="dim", header_style="bold green")
    t_sub1.add_column("Replacement Candidate", style="bold yellow", width=26)
    t_sub1.add_column("Supporting Recipes", justify="center", width=20)
    t_sub1.add_column("Evidence Strength", justify="center", width=18)
    t_sub1.add_column("Sample Supporting Recipe IDs", style="cyan", width=36)
    for c in sub1["substitution_candidates"][:5]:
        sample_ids = ", ".join(c["supporting_recipe_ids"][:3])
        strength_badge = f"[green]{c['evidence_strength']}[/green]" if c['evidence_strength'] == 'strong' else f"[yellow]{c['evidence_strength']}[/yellow]"
        t_sub1.add_row(c["substitute"], f"{c['supporting_recipe_count']} recipes", strength_badge, sample_ids)
    console.print(t_sub1)
    console.print(f"[dim]Overall Evidence Strength: {sub1['evidence_strength_overall'].upper()} | {sub1['disclaimer']}[/dim]")

    # 3B: Pasta cream sauce without dairy
    console.print("\n[bold yellow]3B. Adapt Pasta Sauce: Replace Cream Without Dairy[/bold yellow]")
    sub2 = find_substitution_evidence(
        recipe_id_or_title="pasta cream",
        target_ingredient="cream",
        restrictions=["dairy"],
    )
    t_sub2 = Table(title=f"Substitutes Mined for '{sub2['target_recipe']['title']}' (ID: {sub2['target_recipe']['recipe_id']})", border_style="dim", header_style="bold green")
    t_sub2.add_column("Replacement Candidate", style="bold yellow", width=26)
    t_sub2.add_column("Supporting Recipes", justify="center", width=20)
    t_sub2.add_column("Evidence Strength", justify="center", width=18)
    for c in sub2["substitution_candidates"][:4]:
        strength_badge = f"[green]{c['evidence_strength']}[/green]" if c['evidence_strength'] == 'strong' else f"[yellow]{c['evidence_strength']}[/yellow]"
        t_sub2.add_row(c["substitute"], f"{c['supporting_recipe_count']} recipes", strength_badge)
    console.print(t_sub2)
    console.print(f"[dim]Overall Evidence Strength: {sub2['evidence_strength_overall'].upper()} | Mined across {sub2['similar_without_target_count']} local recipes.[/dim]\n")


# ---------------------------------------------------------------------------
# TASK 4: Grounded Multi-Turn Conversational Agent Demo
# ---------------------------------------------------------------------------
def run_live_agent():
    console.print(Rule("[bold cyan]LIVE CONVERSATIONAL AGENT (Multi-Turn State Retention & Grounding)[/bold cyan]", style="cyan"))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[yellow]GEMINI_API_KEY not configured in .env — skipping live LLM turns.[/yellow]\n")
        return

    from src.agent import create_agent

    console.print("\n[bold]Initializing RecipeAgent with Gemini & SQLite Tools...[/bold]")
    agent = create_agent()
    console.print(f"[dim]Active Model: {agent.model}[/dim]\n")

    # Turn 1
    query_1 = "Find me a penne pasta recipe"
    console.print(f"[bold cyan]User Turn 1:[/bold cyan] {query_1}")
    with console.status("[dim]Processing turn 1...[/dim]", spinner="dots"):
        r1 = agent.chat(query_1)
    preview_1 = "\n".join(r1.strip().split("\n")[:8]) + "\n..."
    console.print(Panel(preview_1, title="[bold green]Assistant Turn 1[/bold green]", border_style="green"))
    console.print(f"[dim]Session State after Turn 1: {agent.state.to_summary()}[/dim]\n")

    # Turn 2
    query_2 = "I cannot have dairy"
    console.print(f"[bold cyan]User Turn 2 (Refinement):[/bold cyan] {query_2}")
    with console.status("[dim]Processing turn 2 with active context...[/dim]", spinner="dots"):
        r2 = agent.chat(query_2)
    preview_2 = "\n".join(r2.strip().split("\n")[:8]) + "\n..."
    console.print(Panel(preview_2, title="[bold green]Assistant Turn 2 (Dairy-Free Refinement)[/bold green]", border_style="green"))
    console.print(f"[dim]Session State after Turn 2: {agent.state.to_summary()}[/dim]\n")


# ---------------------------------------------------------------------------
# Main Runner
# ---------------------------------------------------------------------------
def main():
    t_start = time.time()
    print_header()
    check_prerequisites()

    run_task_1()
    run_task_2()
    run_task_3()
    run_live_agent()

    elapsed = time.time() - t_start
    console.print(Rule("[bold green]ALL TASKS COMPLETED SUCCESSFULLY[/bold green]", style="green"))
    console.print(
        f"\n[bold green]✓ Entire assignment test suite finished in {elapsed:.2f} seconds.[/bold green]\n"
        f"[white]To run the interactive Browser Web UI:[/white] [bold cyan]python web_app.py[/bold cyan]\n"
        f"[white]To run the interactive Terminal CLI:[/white] [bold cyan]python app.py[/bold cyan]\n"
        f"[white]To run the formal evaluation benchmark:[/white] [bold cyan]python eval.py[/bold cyan]\n"
    )


if __name__ == "__main__":
    main()
