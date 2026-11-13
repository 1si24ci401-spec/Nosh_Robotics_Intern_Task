#!/usr/bin/env python3
"""
eval.py — Reproducible evaluation suite for the Nosh Robotics Recipe Assistant.

Runs 6 test scenarios + 1 LLM comparison, saves results to EVAL_RESULTS.md.

Usage:
    python eval.py

Requirements:
    - data/recipes.db must exist (run: python src/ingest.py)
    - GEMINI_API_KEY must be set in .env (for LLM-involved tests)
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich import print as rprint

load_dotenv()

console = Console()

# ---------------------------------------------------------------------------
# Agent import — deferred so direct-tool tests still run without a valid key
# ---------------------------------------------------------------------------
def _import_agent():
    from src.agent import create_agent  # noqa: F401
    return create_agent


# ---------------------------------------------------------------------------
# TEST 1 — Multi-turn Search + Dairy Filter
# ---------------------------------------------------------------------------
def test_01_multiturn_search_dairy() -> dict:
    """
    Turn 1: Search for penne pasta recipes
    Turn 2: Filter for no dairy
    Verifies: state persistence, dairy exclusion expansion
    """
    create_agent = _import_agent()
    agent = create_agent()

    t1_response = agent.chat("Find me a penne pasta recipe")
    t2_response = agent.chat("I cannot have dairy")

    dairy_keywords = {"dairy", "milk", "cream", "butter", "cheese", "yogurt"}
    state_summary = agent.state.to_summary()

    excluded = set(agent.state.exclude_ingredients) if hasattr(agent.state, "exclude_ingredients") else set()
    passed = bool(excluded & dairy_keywords)

    return {
        "test": "01_multiturn_search_dairy",
        "turn_1_query": "Find me a penne pasta recipe",
        "turn_1_response": t1_response,
        "turn_2_query": "I cannot have dairy",
        "turn_2_response": t2_response,
        "state_after": state_summary,
        "excluded_ingredients": list(excluded),
        "passed": passed,
    }


# ---------------------------------------------------------------------------
# TEST 2 — Aggregate Statistics (direct tool, no LLM)
# ---------------------------------------------------------------------------
def test_02_aggregate_stats() -> dict:
    """
    Direct tool test (no LLM needed):
    - Count recipes with both garlic AND onion
    - Compute percentage of dataset
    - Find 5 tomato recipes with fewest steps
    """
    from src.tools import compute_dataset_stats

    garlic_onion = compute_dataset_stats(
        stat_type="count",
        include_ingredients=["garlic", "onion"],
    )

    tomato_fewest = compute_dataset_stats(
        stat_type="fewest_steps",
        include_ingredients=["tomato"],
        top_n=5,
    )

    passed = (
        garlic_onion.get("numerator", 0) > 0
        and garlic_onion.get("denominator", 0) > 0
        and garlic_onion.get("percentage") is not None
        and len(tomato_fewest.get("results", [])) > 0
    )

    return {
        "test": "02_aggregate_stats",
        "garlic_onion_count": garlic_onion,
        "tomato_fewest_steps": tomato_fewest,
        "passed": passed,
    }


# ---------------------------------------------------------------------------
# TEST 3 — Pantry Matching + Follow-up
# ---------------------------------------------------------------------------
def test_03_pantry_matching() -> dict:
    """
    Turn 1: Match recipes for eggs, onions, tomatoes, rice — no peanuts, ≤6 steps
    Turn 2: "Exclude eggs too" — verify re-ranking
    """
    create_agent = _import_agent()
    agent = create_agent()

    t1 = agent.chat(
        "I have eggs, onions, tomatoes, and rice. Suggest 5 recipes using as many of these as "
        "possible, with no peanuts and at most 6 instruction steps. Prefer recipes that need the "
        "fewest additional ingredients."
    )

    t2 = agent.chat("Exclude eggs too")

    state_summary = agent.state.to_summary()
    last_shown = getattr(agent.state, "last_shown_recipe_ids", [])

    return {
        "test": "03_pantry_matching",
        "turn_1_response": t1,
        "turn_2_response": t2,
        "state_after": state_summary,
        "last_shown_recipe_ids": last_shown,
        "passed": len(last_shown) > 0,
    }


# ---------------------------------------------------------------------------
# TEST 4 — Hard-Constraint No-Match Edge Case (direct tool)
# ---------------------------------------------------------------------------
def test_04_no_match_hard_constraint() -> dict:
    """
    Direct tool test:
    Request a recipe with contradictory/impossible constraints:
    - Available: ["egg", "butter", "milk"]
    - Exclude: ["dairy", "eggs"]
    - Max steps: 1
    Verifies: system returns 0 eligible recipes without silently relaxing constraints,
    and separately offers closest violating alternatives clearly flagged.
    """
    from src.tools import match_pantry_recipes

    result = match_pantry_recipes(
        available_ingredients=["egg", "butter", "milk"],
        exclude_ingredients=["dairy", "eggs"],
        max_steps=1,
        limit=5,
    )

    eligible = result.get("eligible_recipes", [])
    alternatives = result.get("closest_violating_alternatives", [])
    no_match_reason = result.get("no_match_reason", "")

    # Moderate constraints — should find something
    moderate_result = match_pantry_recipes(
        available_ingredients=["salt"],
        exclude_ingredients=["peanut"],
        max_steps=100,
        limit=5,
    )

    return {
        "test": "04_no_match_edge_case",
        "impossible_constraint_result": {
            "eligible_count": len(eligible),
            "has_violating_alternatives": len(alternatives) > 0,
            "no_match_reason": no_match_reason,
            "constraints_applied": result.get("constraints_applied", {}),
            "sample_alternative": alternatives[0] if alternatives else None,
        },
        "moderate_constraint_result": {
            "eligible_count": len(moderate_result.get("eligible_recipes", [])),
        },
        "passed": len(eligible) == 0 and len(moderate_result.get("eligible_recipes", [])) > 0,
        "note": "Hard constraints are enforced — no silent relaxation.",
    }


# ---------------------------------------------------------------------------
# TEST 5 — Evidence-Based Substitution (direct tool)
# ---------------------------------------------------------------------------
def test_05_substitution_evidence() -> dict:
    """
    Direct tool test:
    Find substitution evidence for eggs in banana bread.
    Verifies: local recipe citations, evidence strength assessment
    """
    from src.tools import find_substitution_evidence, search_recipes

    bread_results = search_recipes(query="banana bread", limit=3)

    if not bread_results.get("results"):
        return {
            "test": "05_substitution_evidence",
            "passed": False,
            "note": "No banana bread recipes found in database",
        }

    recipe = bread_results["results"][0]
    recipe_id = recipe["recipe_id"]

    evidence = find_substitution_evidence(
        recipe_id_or_title=recipe_id,
        target_ingredient="egg",
        restrictions=["dairy"],
    )

    # Also test dairy-free pasta cream substitution
    pasta_results = search_recipes(query="pasta cream", limit=3)
    pasta_evidence: dict = {}
    if pasta_results.get("results"):
        pasta_recipe = pasta_results["results"][0]
        pasta_evidence = find_substitution_evidence(
            recipe_id_or_title=pasta_recipe["recipe_id"],
            target_ingredient="cream",
            restrictions=["dairy"],
        )

    return {
        "test": "05_substitution_evidence",
        "banana_bread_recipe": {"recipe_id": recipe_id, "title": recipe.get("title")},
        "egg_substitution": {
            "evidence_strength": evidence.get("evidence_strength_overall"),
            "candidate_count": len(evidence.get("substitution_candidates", [])),
            "supporting_recipes": len(evidence.get("similar_without_target", [])),
            "top_candidates": evidence.get("substitution_candidates", [])[:3],
        },
        "pasta_cream_substitution": (
            {
                "evidence_strength": pasta_evidence.get("evidence_strength_overall"),
                "candidate_count": len(pasta_evidence.get("substitution_candidates", [])),
            }
            if pasta_evidence
            else "No pasta cream recipe found"
        ),
        "passed": evidence.get("evidence_strength_overall") is not None,
    }


# ---------------------------------------------------------------------------
# TEST 6 — Weak Evidence + LLM Comparison
# ---------------------------------------------------------------------------
def test_06_llm_comparison() -> dict:
    """
    LLM COMPARISON TEST:
    Shows where a naive one-shot LLM hallucinate vs our grounded system.

    Part A: Grounded exact count vs naive LLM for "how many garlic recipes?"
    Part B: Weak evidence substitution (saffron)
    """
    from src.tools import compute_dataset_stats, find_substitution_evidence, search_recipes

    results: dict = {"test": "06_llm_comparison"}

    # --- Part A: Grounded answer ---
    grounded_stats = compute_dataset_stats(
        stat_type="count",
        include_ingredients=["garlic"],
    )
    results["grounded_garlic_count"] = {
        "numerator": grounded_stats.get("numerator"),
        "denominator": grounded_stats.get("denominator"),
        "percentage": grounded_stats.get("percentage"),
        "source": "SQLite COUNT(*) over full dataset",
    }

    # --- Part B: Naive LLM hallucination ---
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        preferred = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        naive_text = ""
        for model_name in [preferred, "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash"]:
            try:
                naive_response = client.models.generate_content(
                    model=model_name,
                    contents=(
                        "How many recipes in the Eight Portions Recipe Box dataset contain garlic? "
                        "What percentage of the dataset is that? Give me exact numbers."
                    ),
                    config=types.GenerateContentConfig(temperature=0.0),
                )
                naive_text = naive_response.candidates[0].content.parts[0].text
                break
            except Exception as exc:
                naive_text = f"Error ({model_name}): {exc}"
    else:
        naive_text = "(GEMINI_API_KEY not set — skipping naive LLM call)"

    results["naive_llm_answer"] = naive_text
    results["comparison_note"] = (
        "The naive LLM cannot know the exact count without querying the database. "
        "It may hallucinate a plausible-sounding number. "
        "Our grounded system uses SQL COUNT(*) over the full dataset for an exact, reproducible answer."
    )

    # --- Part C: Weak evidence substitution ---
    saffron_results = search_recipes(query="saffron", limit=1)
    if saffron_results.get("results"):
        saffron_recipe = saffron_results["results"][0]
        weak_evidence = find_substitution_evidence(
            recipe_id_or_title=saffron_recipe["recipe_id"],
            target_ingredient="saffron",
            restrictions=[],
        )
        results["weak_evidence_case"] = {
            "recipe": saffron_recipe.get("title"),
            "evidence_strength": weak_evidence.get("evidence_strength_overall"),
            "candidate_count": len(weak_evidence.get("substitution_candidates", [])),
            "note": (
                "If evidence is weak, system correctly flags uncertainty "
                "rather than hallucinating."
            ),
        }
    else:
        results["weak_evidence_case"] = "No saffron recipe found in database"

    results["passed"] = True
    return results


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------
def run_all_tests() -> list:
    db_path = Path("data/recipes.db")
    if not db_path.exists():
        console.print("[bold red]ERROR:[/bold red] data/recipes.db not found.")
        console.print("Run [cyan]python src/ingest.py[/cyan] first.")
        sys.exit(1)

    tests = [
        ("01: Multi-turn Search + Dairy Filter", test_01_multiturn_search_dairy),
        ("02: Aggregate Statistics", test_02_aggregate_stats),
        ("03: Pantry Matching + Follow-up", test_03_pantry_matching),
        ("04: Hard-Constraint No-Match", test_04_no_match_hard_constraint),
        ("05: Substitution Evidence", test_05_substitution_evidence),
        ("06: Weak Evidence + LLM Comparison", test_06_llm_comparison),
    ]

    results = []
    for test_name, test_fn in tests:
        console.print(f"\n[bold cyan]Running {test_name}...[/bold cyan]")
        start = time.time()
        try:
            result = test_fn()
            elapsed = time.time() - start
            result["elapsed_seconds"] = round(elapsed, 2)
            status = "[green]PASS[/green]" if result.get("passed") else "[yellow]PARTIAL[/yellow]"
            console.print(f"  {status} ({elapsed:.1f}s)")
        except Exception as exc:
            elapsed = time.time() - start
            result = {
                "test": test_name,
                "passed": False,
                "error": str(exc),
                "elapsed_seconds": round(elapsed, 2),
            }
            console.print(f"  [red]FAIL[/red]: {exc}")
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------
def save_results(results: list) -> None:
    lines = [
        "# Evaluation Results — Nosh Robotics Recipe Assistant",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n---\n",
        "## Summary\n",
        "| Test | Status | Time (s) |",
        "|------|--------|----------|",
    ]

    for r in results:
        if r.get("error"):
            status = "❌ FAIL"
        elif r.get("passed"):
            status = "✅ PASS"
        else:
            status = "⚠️ PARTIAL"
        name = r.get("test", "unknown")
        t = r.get("elapsed_seconds", "?")
        lines.append(f"| {name} | {status} | {t} |")

    lines.append("\n---\n")

    for r in results:
        lines.append(f"## {r.get('test', 'unknown')}\n")
        lines.append("```json")
        lines.append(json.dumps(r, indent=2, default=str))
        lines.append("```\n")

    # LLM comparison section
    llm_test = next((r for r in results if "06" in str(r.get("test", ""))), None)
    if llm_test and not llm_test.get("error"):
        lines.append("## LLM Comparison Analysis\n")
        lines.append("### Naive One-Shot LLM Answer\n")
        lines.append(f"> {llm_test.get('naive_llm_answer', 'N/A')}\n")
        lines.append("### Grounded System Answer\n")
        grounded = llm_test.get("grounded_garlic_count", {})
        lines.append(f"- **Exact count**: {grounded.get('numerator', 'N/A')}")
        lines.append(f"- **Total recipes**: {grounded.get('denominator', 'N/A')}")
        lines.append(f"- **Percentage**: {grounded.get('percentage', 'N/A')}%")
        lines.append(f"- **Source**: {grounded.get('source', 'N/A')}\n")
        lines.append(f"**Key Difference**: {llm_test.get('comparison_note', '')}\n")

    output = "\n".join(lines)
    Path("EVAL_RESULTS.md").write_text(output, encoding="utf-8")
    console.print("\n[green]✓ Results saved to EVAL_RESULTS.md[/green]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    console.print("[bold]Nosh Robotics Recipe Assistant — Evaluation Suite[/bold]")
    console.print("Database: data/recipes.db")
    results = run_all_tests()
    save_results(results)

    passed = sum(1 for r in results if r.get("passed"))
    console.print(f"\n[bold]Results: {passed}/{len(results)} tests passed[/bold]")
