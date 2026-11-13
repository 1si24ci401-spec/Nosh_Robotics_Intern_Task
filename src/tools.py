"""
src/tools.py
~~~~~~~~~~~~
Deterministic Python + SQLite tool functions exposed to the Gemini agent.
No LLM calls occur inside this module — all counts, rankings, pantry scores,
and substitution evidence are computed programmatically over data/recipes.db.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from src.normalize import DIETARY_GROUPS, NON_DAIRY_EXCEPTIONS, normalize_ingredient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "recipes.db"

logger = logging.getLogger(__name__)

SCORING_FORMULA_DESC = "score = (2.0 * matched) - (1.0 * extra_required) - (0.15 * step_count)"
STEP_COUNTING_RULE = (
    "Split instructions on newlines and sentence boundaries ([.!?]\\s+); "
    "count fragments >= 4 chars containing at least one ASCII letter."
)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Helpers: Exclusion expansion & SQL predicate builder
# ---------------------------------------------------------------------------

def _expand_exclusions(exclude_items: list[str]) -> tuple[set[str], set[str]]:
    """
    Normalize each exclusion item and expand dietary group keywords.
    Returns (expanded_norm_names, raw_group_keys_lower).
    """
    expanded: set[str] = set()
    groups: set[str] = set()
    for item in exclude_items:
        raw_lower = item.strip().lower()
        # Strip leading "no " or "without " if LLM passes "no dairy"
        for prefix in ("no ", "without ", "free of "):
            if raw_lower.startswith(prefix):
                raw_lower = raw_lower[len(prefix):].strip()

        norm = normalize_ingredient(raw_lower)[0]
        if raw_lower in DIETARY_GROUPS:
            groups.add(raw_lower)
            expanded.update(DIETARY_GROUPS[raw_lower])
        elif norm in DIETARY_GROUPS:
            groups.add(norm)
            expanded.update(DIETARY_GROUPS[norm])
        else:
            if norm:
                expanded.add(norm)
            if raw_lower and raw_lower != norm:
                expanded.add(raw_lower)
    return expanded, groups


def _exclusion_sql_predicate(
    expanded_exclusions: set[str],
    group_keys: set[str],
    table_alias: str = "r",
) -> tuple[str, list[Any]]:
    """
    Build SQL NOT IN predicates for hard ingredient/dietary exclusions.
    Handles compound ingredient names (e.g. 'monterey jack cheese' for dairy,
    'peanut butter' for peanut, 'egg yolk' for egg without catching 'eggplant').
    """
    if not expanded_exclusions and not group_keys:
        return "", []

    clauses: list[str] = []
    params: list[Any] = []

    if expanded_exclusions:
        placeholders = ",".join("?" * len(expanded_exclusions))
        clauses.append(
            f" AND {table_alias}.recipe_id NOT IN ("
            f"SELECT recipe_id FROM recipe_ingredients WHERE norm_name IN ({placeholders}))"
        )
        params.extend(sorted(expanded_exclusions))

    if "dairy" in group_keys:
        exc_list = sorted(NON_DAIRY_EXCEPTIONS)
        exc_ph = ",".join("?" * len(exc_list))
        clauses.append(
            f" AND {table_alias}.recipe_id NOT IN ("
            f"SELECT recipe_id FROM recipe_ingredients WHERE ("
            f"norm_name LIKE '%cheese%' OR norm_name LIKE '%cream%' OR "
            f"norm_name LIKE '%milk%' OR norm_name LIKE '%butter%' OR "
            f"norm_name LIKE '%yogurt%' OR norm_name LIKE '%parmigiano%' OR "
            f"norm_name LIKE '%parmesan%' OR norm_name LIKE '%pecorino%' OR "
            f"norm_name LIKE '%mozzarella%' OR norm_name LIKE '%cheddar%' OR "
            f"norm_name LIKE '%ricotta%' OR norm_name LIKE '%gruyere%' OR "
            f"norm_name LIKE '%feta%' OR norm_name LIKE '%mascarpone%') "
            f"AND norm_name NOT IN ({exc_ph}))"
        )
        params.extend(exc_list)

    if "peanut" in group_keys or "peanuts" in group_keys or "peanut" in expanded_exclusions:
        clauses.append(
            f" AND {table_alias}.recipe_id NOT IN ("
            f"SELECT recipe_id FROM recipe_ingredients WHERE norm_name LIKE '%peanut%')"
        )

    if "egg" in group_keys or "eggs" in group_keys or "egg" in expanded_exclusions:
        # Match whole-word 'egg'/'eggs' so 'eggplant' and 'nutmeg' are NOT excluded
        clauses.append(
            f" AND {table_alias}.recipe_id NOT IN ("
            f"SELECT recipe_id FROM recipe_ingredients WHERE "
            f"norm_name = 'egg' OR norm_name LIKE 'egg %' OR "
            f"norm_name LIKE '% egg' OR norm_name LIKE '% egg %')"
        )

    return "".join(clauses), params


def _fts_tokens_query(query: str, operator: str = "AND") -> str:
    """Build a safe FTS5 MATCH query from alphanumeric tokens."""
    tokens = re.findall(r"[a-zA-Z0-9]+", query)
    if not tokens:
        return ""
    quoted = [f'"{t}"' for t in tokens]
    if operator == "OR" and len(quoted) > 1:
        return " OR ".join(quoted)
    return " ".join(quoted)


def _ingredient_filter_clause(
    norm_includes: list[str],
    expanded_exclusions: set[str],
    group_keys: set[str],
    max_steps: int | None,
    table_alias: str = "r",
) -> tuple[str, list[Any]]:
    """Return (clause_fragment, params) to append after an existing WHERE 1=1."""
    clause = ""
    params: list[Any] = []
    for norm in norm_includes:
        clause += (
            f" AND {table_alias}.recipe_id IN "
            f"(SELECT recipe_id FROM recipe_ingredients WHERE norm_name = ?)"
        )
        params.append(norm)

    exc_clause, exc_params = _exclusion_sql_predicate(
        expanded_exclusions, group_keys, table_alias=table_alias
    )
    clause += exc_clause
    params.extend(exc_params)

    if max_steps is not None:
        clause += f" AND {table_alias}.step_count <= ?"
        params.append(max_steps)

    return clause, params


# ---------------------------------------------------------------------------
# FUNCTION 1: search_recipes
# ---------------------------------------------------------------------------

def search_recipes(
    query: str = "",
    include_ingredients: list[str] | None = None,
    exclude_ingredients: list[str] | None = None,
    max_steps: int | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search recipes using SQLite FTS5 and normalized ingredient filters."""
    norm_includes: list[str] = []
    if include_ingredients:
        for ing in include_ingredients:
            norm = normalize_ingredient(ing)[0]
            if norm:
                norm_includes.append(norm)

    expanded_exclusions: set[str] = set()
    group_keys: set[str] = set()
    if exclude_ingredients:
        expanded_exclusions, group_keys = _expand_exclusions(exclude_ingredients)

    filter_clause, filter_params = _ingredient_filter_clause(
        norm_includes, expanded_exclusions, group_keys, max_steps, table_alias="r"
    )

    fts_query = _fts_tokens_query(query, operator="AND") if query and query.strip() else ""
    rows = []

    try:
        conn = get_conn()
        try:
            if fts_query:
                sql = (
                    "SELECT r.recipe_id, r.title, r.step_count, r.ingredients_raw, r.instructions_raw "
                    "FROM recipes r "
                    "JOIN recipes_fts fts ON fts.recipe_id = r.recipe_id "
                    f"WHERE recipes_fts MATCH ?{filter_clause} "
                    "ORDER BY bm25(recipes_fts, 0.0, 10.0, 3.0, 1.0) LIMIT ?"
                )
                try:
                    rows = conn.execute(sql, [fts_query] + filter_params + [limit]).fetchall()
                except sqlite3.OperationalError as fts_err:
                    logger.warning("FTS5 error (%s), falling back to LIKE search.", fts_err)
                    like_q = f"%{query.strip()}%"
                    fb_sql = (
                        "SELECT r.recipe_id, r.title, r.step_count, r.ingredients_raw, r.instructions_raw "
                        "FROM recipes r "
                        f"WHERE (r.title LIKE ? OR r.instructions_raw LIKE ?){filter_clause} "
                        "LIMIT ?"
                    )
                    rows = conn.execute(fb_sql, [like_q, like_q] + filter_params + [limit]).fetchall()
            else:
                sql = (
                    "SELECT r.recipe_id, r.title, r.step_count, r.ingredients_raw, r.instructions_raw "
                    f"FROM recipes r WHERE 1=1{filter_clause} LIMIT ?"
                )
                rows = conn.execute(sql, filter_params + [limit]).fetchall()
        finally:
            conn.close()
    except Exception as e:
        logger.error("search_recipes error: %s", e)
        return {
            "results": [],
            "count": 0,
            "error": str(e),
            "filters_applied": {
                "query": query,
                "include_ingredients": include_ingredients or [],
                "exclude_ingredients": exclude_ingredients or [],
                "max_steps": max_steps,
                "expanded_exclusions": sorted(expanded_exclusions),
            },
        }

    results = []
    for row in rows:
        try:
            ing_list = json.loads(row["ingredients_raw"])
        except (json.JSONDecodeError, TypeError):
            ing_list = []
        results.append(
            {
                "recipe_id": row["recipe_id"],
                "title": row["title"],
                "step_count": row["step_count"],
                "ingredients_raw": ing_list,
                "instructions_raw": row["instructions_raw"],
            }
        )

    return {
        "results": results,
        "count": len(results),
        "filters_applied": {
            "query": query,
            "include_ingredients": include_ingredients or [],
            "include_normalized": norm_includes,
            "exclude_ingredients": exclude_ingredients or [],
            "max_steps": max_steps,
            "expanded_exclusions": sorted(expanded_exclusions),
            "dietary_groups_expanded": sorted(group_keys),
        },
    }


# ---------------------------------------------------------------------------
# FUNCTION 2: compute_dataset_stats
# ---------------------------------------------------------------------------

def compute_dataset_stats(
    stat_type: str,
    include_ingredients: list[str] | None = None,
    exclude_ingredients: list[str] | None = None,
    group_by: str | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Compute exact dataset statistics over the complete filtered SQLite result set."""
    norm_includes: list[str] = []
    if include_ingredients:
        for ing in include_ingredients:
            norm = normalize_ingredient(ing)[0]
            if norm:
                norm_includes.append(norm)

    expanded_exclusions: set[str] = set()
    group_keys: set[str] = set()
    if exclude_ingredients:
        expanded_exclusions, group_keys = _expand_exclusions(exclude_ingredients)

    filters_applied = {
        "include_ingredients": include_ingredients or [],
        "include_normalized": norm_includes,
        "exclude_ingredients": exclude_ingredients or [],
        "expanded_exclusions": sorted(expanded_exclusions),
        "group_by": group_by,
    }
    normalization_note = (
        "Ingredient names normalized via normalize_ingredient() "
        "(strips quantities, units, prep adjectives, parentheticals, and maps plurals/aliases "
        "such as tomatoes->tomato, garlic cloves->garlic, onions->onion)."
    )

    filter_clause, filter_params = _ingredient_filter_clause(
        norm_includes, expanded_exclusions, group_keys, None, table_alias="r"
    )

    try:
        conn = get_conn()
        try:
            total_recipes = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]

            if stat_type == "count":
                sql = f"SELECT COUNT(*) FROM recipes r WHERE 1=1{filter_clause}"
                n = conn.execute(sql, filter_params).fetchone()[0]
                percentage = round(n / total_recipes * 100, 2) if total_recipes else 0.0
                out: dict[str, Any] = {
                    "stat_type": "count",
                    "numerator": n,
                    "denominator": total_recipes,
                    "percentage": percentage,
                    "filters_applied": filters_applied,
                    "total_recipes_in_dataset": total_recipes,
                    "normalization_note": normalization_note,
                }
                if group_by == "source":
                    grp_sql = (
                        f"SELECT r.source, COUNT(*) as cnt FROM recipes r "
                        f"WHERE 1=1{filter_clause} GROUP BY r.source ORDER BY cnt DESC"
                    )
                    out["breakdown_by_source"] = [
                        {"source": row["source"], "count": row["cnt"]}
                        for row in conn.execute(grp_sql, filter_params).fetchall()
                    ]
                return out

            elif stat_type == "common_ingredients":
                sql = (
                    "SELECT ri.norm_name, COUNT(DISTINCT ri.recipe_id) as freq "
                    "FROM recipe_ingredients ri "
                    "JOIN recipes r ON r.recipe_id = ri.recipe_id "
                    f"WHERE ri.norm_name != ''{filter_clause} "
                    "GROUP BY ri.norm_name ORDER BY freq DESC LIMIT ?"
                )
                rows = conn.execute(sql, filter_params + [top_n]).fetchall()
                count_sql = f"SELECT COUNT(*) FROM recipes r WHERE 1=1{filter_clause}"
                analyzed = conn.execute(count_sql, filter_params).fetchone()[0]
                return {
                    "stat_type": "common_ingredients",
                    "top_n": top_n,
                    "results": [
                        {"ingredient": row["norm_name"], "recipe_count": row["freq"]}
                        for row in rows
                    ],
                    "total_recipes_analyzed": analyzed,
                    "total_recipes_in_dataset": total_recipes,
                    "normalization_note": normalization_note,
                    "filters_applied": filters_applied,
                }

            elif stat_type == "avg_ingredients":
                sql = (
                    "SELECT AVG(ingredient_count), MIN(ingredient_count), MAX(ingredient_count), "
                    f"COUNT(*) FROM recipes r WHERE 1=1{filter_clause}"
                )
                row = conn.execute(sql, filter_params).fetchone()
                avg_val = round(row[0], 2) if row[0] is not None else 0
                min_val = row[1] or 0
                max_val = row[2] or 0
                n_recipes = row[3] or 0

                med_sql = (
                    f"SELECT ingredient_count FROM recipes r WHERE 1=1{filter_clause} "
                    "ORDER BY ingredient_count"
                )
                vals = [r[0] for r in conn.execute(med_sql, filter_params).fetchall()]
                if vals:
                    mid = len(vals) // 2
                    median = vals[mid] if len(vals) % 2 == 1 else (vals[mid - 1] + vals[mid]) / 2
                else:
                    median = 0
                return {
                    "stat_type": "avg_ingredients",
                    "average": avg_val,
                    "median": median,
                    "min": min_val,
                    "max": max_val,
                    "total_recipes_analyzed": n_recipes,
                    "total_recipes_in_dataset": total_recipes,
                    "normalization_note": normalization_note,
                    "filters_applied": filters_applied,
                }

            elif stat_type in ("fewest_steps", "most_steps"):
                order = "ASC" if stat_type == "fewest_steps" else "DESC"
                step_guard = " AND r.step_count > 0" if stat_type == "fewest_steps" else ""
                sql = (
                    f"SELECT r.recipe_id, r.title, r.step_count, r.instructions_raw FROM recipes r "
                    f"WHERE 1=1{step_guard}{filter_clause} "
                    f"ORDER BY r.step_count {order}, r.recipe_id ASC LIMIT ?"
                )
                rows = conn.execute(sql, filter_params + [top_n]).fetchall()
                count_sql = f"SELECT COUNT(*) FROM recipes r WHERE 1=1{step_guard}{filter_clause}"
                analyzed = conn.execute(count_sql, filter_params).fetchone()[0]
                return {
                    "stat_type": stat_type,
                    "results": [
                        {
                            "rank": i + 1,
                            "recipe_id": row["recipe_id"],
                            "title": row["title"],
                            "step_count": row["step_count"],
                            "instructions_snippet": (row["instructions_raw"] or "")[:200],
                        }
                        for i, row in enumerate(rows)
                    ],
                    "total_recipes_analyzed": analyzed,
                    "total_recipes_in_dataset": total_recipes,
                    "step_counting_rule": STEP_COUNTING_RULE,
                    "normalization_note": normalization_note,
                    "filters_applied": filters_applied,
                }

            else:
                return {
                    "error": f"Unknown stat_type: {stat_type!r}",
                    "valid_stat_types": [
                        "count",
                        "common_ingredients",
                        "avg_ingredients",
                        "fewest_steps",
                        "most_steps",
                    ],
                }
        finally:
            conn.close()
    except Exception as e:
        logger.error("compute_dataset_stats error: %s", e)
        return {"error": str(e), "stat_type": stat_type}


# ---------------------------------------------------------------------------
# FUNCTION 3: match_pantry_recipes
# ---------------------------------------------------------------------------

def match_pantry_recipes(
    available_ingredients: list[str],
    exclude_ingredients: list[str] | None = None,
    max_steps: int | None = None,
    prefer_fewer_steps: bool = True,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Match and rank recipes against available pantry ingredients.
    Hard constraints (exclude_ingredients, max_steps) are enforced strictly in SQL
    and never silently relaxed.
    """
    pantry: set[str] = set()
    quantities_provided: list[dict[str, Any]] = []
    for ing in available_ingredients:
        norm, qty, unit = normalize_ingredient(ing)
        if norm:
            pantry.add(norm)
            if qty or unit:
                quantities_provided.append(
                    {"raw": ing, "norm_name": norm, "quantity": qty, "unit": unit}
                )

    expanded_exclusions: set[str] = set()
    group_keys: set[str] = set()
    if exclude_ingredients:
        expanded_exclusions, group_keys = _expand_exclusions(exclude_ingredients)

    qty_note = (
        "Name-level match only; quantity sufficiency not verified "
        "(recipe units/yields vary across sources and cannot be reliably compared)."
    )

    def _run_query(apply_constraints: bool) -> list[sqlite3.Row]:
        sql = (
            "SELECT r.recipe_id, r.title, r.step_count, "
            "GROUP_CONCAT(ri.norm_name, '||') as norm_ingredients "
            "FROM recipes r "
            "JOIN recipe_ingredients ri ON ri.recipe_id = r.recipe_id "
            "WHERE 1=1"
        )
        params: list[Any] = []
        # Pre-filter to recipes that share at least 1 pantry ingredient for speed & relevance
        if pantry:
            p_ph = ",".join("?" * len(pantry))
            sql += (
                f" AND r.recipe_id IN ("
                f"SELECT recipe_id FROM recipe_ingredients WHERE norm_name IN ({p_ph}))"
            )
            params.extend(sorted(pantry))

        if apply_constraints:
            exc_clause, exc_params = _exclusion_sql_predicate(
                expanded_exclusions, group_keys, table_alias="r"
            )
            sql += exc_clause
            params.extend(exc_params)
            if max_steps is not None:
                sql += " AND r.step_count <= ?"
                params.append(max_steps)

        sql += " GROUP BY r.recipe_id"
        return conn.execute(sql, params).fetchall()

    try:
        conn = get_conn()
        try:
            eligible_rows = _run_query(apply_constraints=True) if pantry else []

            scored: list[dict[str, Any]] = []
            for row in eligible_rows:
                raw_norm_ings = row["norm_ingredients"] or ""
                recipe_ingredients_set = {
                    x for x in raw_norm_ings.split("||") if x
                }
                matched = pantry & recipe_ingredients_set
                if not matched:
                    continue
                extra_required = recipe_ingredients_set - pantry
                unused_pantry = pantry - recipe_ingredients_set
                step_count = row["step_count"] or 0
                score = round(
                    (2.0 * len(matched)) - (1.0 * len(extra_required)) - (0.15 * step_count),
                    3,
                )
                extra_sorted = sorted(extra_required)
                scored.append(
                    {
                        "recipe_id": row["recipe_id"],
                        "title": row["title"],
                        "step_count": step_count,
                        "matched_ingredients": sorted(matched),
                        "missing_from_pantry": extra_sorted,
                        "extra_required_ingredients": extra_sorted,
                        "unused_pantry_ingredients": sorted(unused_pantry),
                        "score": score,
                        "ranking_explanation": (
                            f"Score={score}: {len(matched)} matched (x2.0) - "
                            f"{len(extra_required)} extra (x1.0) - {step_count} steps (x0.15)"
                        ),
                        "quantity_verification": qty_note,
                    }
                )

            total_eligible_count = len(scored)
            scored.sort(
                key=lambda x: (-x["score"], x["step_count"] if prefer_fewer_steps else 0)
            )
            # Deduplicate identical titles (e.g. duplicate dataset entries) when picking top-K
            top_results: list[dict[str, Any]] = []
            seen_titles: set[str] = set()
            for item in scored:
                t_key = item["title"].strip().lower()
                if t_key in seen_titles:
                    continue
                seen_titles.add(t_key)
                top_results.append(item)
                if len(top_results) >= limit:
                    break

            if not top_results:
                all_rows = _run_query(apply_constraints=False) if pantry else []
                alt_scored: list[dict[str, Any]] = []
                for row in all_rows:
                    raw_norm_ings = row["norm_ingredients"] or ""
                    recipe_ingredients_set = {
                        x for x in raw_norm_ings.split("||") if x
                    }
                    matched = pantry & recipe_ingredients_set
                    extra_required = recipe_ingredients_set - pantry
                    step_count = row["step_count"] or 0
                    score = round(
                        (2.0 * len(matched)) - (1.0 * len(extra_required)) - (0.15 * step_count),
                        3,
                    )
                    violations: list[str] = []
                    hit_excludes = recipe_ingredients_set & expanded_exclusions
                    if "dairy" in group_keys:
                        hit_excludes |= {
                            ing for ing in recipe_ingredients_set
                            if any(k in ing for k in ("cheese", "cream", "milk", "butter", "yogurt"))
                            and ing not in NON_DAIRY_EXCEPTIONS
                        }
                    if "peanut" in group_keys or "peanuts" in group_keys or "peanut" in expanded_exclusions:
                        hit_excludes |= {ing for ing in recipe_ingredients_set if "peanut" in ing}
                    if "egg" in group_keys or "eggs" in group_keys or "egg" in expanded_exclusions:
                        hit_excludes |= {
                            ing for ing in recipe_ingredients_set
                            if ing == "egg" or ing.startswith("egg ") or ing.endswith(" egg") or " egg " in ing
                        }

                    if hit_excludes:
                        violations.append(
                            f"contains excluded ingredients: {sorted(hit_excludes)}"
                        )
                    if max_steps is not None and step_count > max_steps:
                        violations.append(
                            f"step_count {step_count} exceeds max_steps {max_steps}"
                        )
                    alt_scored.append(
                        {
                            "recipe_id": row["recipe_id"],
                            "title": row["title"],
                            "step_count": step_count,
                            "matched_ingredients": sorted(matched),
                            "missing_from_pantry": sorted(extra_required),
                            "score": score,
                            "violated_constraints": violations,
                        }
                    )
                alt_scored.sort(key=lambda x: -x["score"])
                return {
                    "eligible_recipes": [],
                    "closest_violating_alternatives": alt_scored[:3],
                    "no_match_reason": (
                        "No recipes satisfy all hard constraints "
                        "(exclude_ingredients and/or max_steps)."
                    ),
                    "constraints_applied": {
                        "exclude_ingredients": exclude_ingredients or [],
                        "expanded_exclusions": sorted(expanded_exclusions),
                        "max_steps": max_steps,
                        "pantry_normalized": sorted(pantry),
                    },
                    "quantities_provided": quantities_provided,
                    "quantity_verification": qty_note,
                    "total_eligible_before_ranking": 0,
                    "scoring_formula": SCORING_FORMULA_DESC,
                }

            return {
                "eligible_recipes": top_results,
                "constraints_applied": {
                    "exclude_ingredients": exclude_ingredients or [],
                    "expanded_exclusions": sorted(expanded_exclusions),
                    "max_steps": max_steps,
                    "pantry_normalized": sorted(pantry),
                },
                "quantities_provided": quantities_provided,
                "quantity_verification": qty_note,
                "total_eligible_before_ranking": total_eligible_count,
                "scoring_formula": SCORING_FORMULA_DESC,
            }
        finally:
            conn.close()
    except Exception as e:
        logger.error("match_pantry_recipes error: %s", e)
        return {"error": str(e), "eligible_recipes": []}


# ---------------------------------------------------------------------------
# FUNCTION 4: find_substitution_evidence
# ---------------------------------------------------------------------------

def find_substitution_evidence(
    recipe_id_or_title: str,
    target_ingredient: str,
    restrictions: list[str] | None = None,
) -> dict[str, Any]:
    """
    Mine the local SQLite dataset for evidence-based ingredient substitutions.
    Compares ingredient frequencies in similar recipes WITHOUT target_ingredient
    against similar recipes WITH target_ingredient.
    """
    try:
        conn = get_conn()
        try:
            # 1. Locate target recipe (exact ID, shortest LIKE title match, or FTS5 fallback)
            recipe_row = conn.execute(
                "SELECT * FROM recipes WHERE recipe_id = ? LIMIT 1",
                (recipe_id_or_title,),
            ).fetchone()

            if recipe_row is None:
                fts_lookup = _fts_tokens_query(recipe_id_or_title, operator="AND")
                if fts_lookup:
                    try:
                        recipe_row = conn.execute(
                            "SELECT r.* FROM recipes r "
                            "JOIN recipes_fts fts ON fts.recipe_id = r.recipe_id "
                            "WHERE recipes_fts MATCH ? "
                            "ORDER BY bm25(recipes_fts, 0.0, 10.0, 3.0, 1.0) LIMIT 1",
                            (fts_lookup,),
                        ).fetchone()
                    except sqlite3.OperationalError:
                        recipe_row = None

            if recipe_row is None:
                recipe_row = conn.execute(
                    "SELECT * FROM recipes WHERE title LIKE ? ORDER BY LENGTH(title) ASC LIMIT 1",
                    (f"%{recipe_id_or_title}%",),
                ).fetchone()

            if recipe_row is None:
                return {
                    "error": "Recipe not found",
                    "recipe_id_or_title": recipe_id_or_title,
                }

            recipe_id = recipe_row["recipe_id"]
            recipe_title = recipe_row["title"]
            try:
                ingredients_raw = json.loads(recipe_row["ingredients_raw"])
            except (json.JSONDecodeError, TypeError):
                ingredients_raw = []

            # 2. Target recipe's normalized ingredients
            target_recipe_norm_ings = {
                r["norm_name"]
                for r in conn.execute(
                    "SELECT norm_name FROM recipe_ingredients WHERE recipe_id = ? AND norm_name != ''",
                    (recipe_id,),
                ).fetchall()
            }

            # 3. Normalize target ingredient
            norm_target = normalize_ingredient(target_ingredient)[0]

            # 4. Build restriction exclusion SQL (plus target-variant exclusion for without-target query)
            restriction_clause = ""
            restriction_params: list[Any] = []
            if restrictions:
                expanded_rest, rest_groups = _expand_exclusions(restrictions)
                restriction_clause, restriction_params = _exclusion_sql_predicate(
                    expanded_rest, rest_groups, table_alias="r"
                )

            target_exp, target_groups = _expand_exclusions([target_ingredient])
            target_excl_clause, target_excl_params = _exclusion_sql_predicate(
                target_exp, target_groups, table_alias="r"
            )

            # 5. Build FTS queries from title words
            stop_words = {"the", "a", "an", "and", "or", "with", "in", "of", "for", "to", "easy", "best"}
            title_words = [
                w for w in re.findall(r"[a-zA-Z0-9]+", recipe_title.lower())
                if w not in stop_words and len(w) > 2
            ][:4]
            fts_and_query = " ".join(f'"{w}"' for w in title_words) if title_words else _fts_tokens_query(recipe_title)
            fts_or_query = " OR ".join(f'"{w}"' for w in title_words) if len(title_words) > 1 else fts_and_query

            def _fetch_similar(has_target: bool, fts_q: str) -> list[sqlite3.Row]:
                target_cond = "IN" if has_target else "NOT IN"
                extra_clause = "" if has_target else target_excl_clause
                extra_params = [] if has_target else target_excl_params
                if fts_q:
                    fts_sql = (
                        "SELECT r.recipe_id, r.title, r.step_count, r.ingredients_raw "
                        "FROM recipes r "
                        "JOIN recipes_fts fts ON fts.recipe_id = r.recipe_id "
                        f"WHERE recipes_fts MATCH ? "
                        f"AND r.recipe_id {target_cond} "
                        "(SELECT recipe_id FROM recipe_ingredients WHERE norm_name = ?) "
                        f"AND r.recipe_id != ?"
                        f"{restriction_clause}{extra_clause} "
                        f"ORDER BY bm25(recipes_fts, 0.0, 10.0, 3.0, 1.0) LIMIT 25"
                    )
                    try:
                        return conn.execute(
                            fts_sql,
                            [fts_q, norm_target, recipe_id] + restriction_params + extra_params,
                        ).fetchall()
                    except sqlite3.OperationalError:
                        pass

                like_term = title_words[0] if title_words else recipe_title
                like_sql = (
                    "SELECT r.recipe_id, r.title, r.step_count, r.ingredients_raw "
                    "FROM recipes r "
                    "WHERE r.title LIKE ? "
                    f"AND r.recipe_id {target_cond} "
                    "(SELECT recipe_id FROM recipe_ingredients WHERE norm_name = ?) "
                    f"AND r.recipe_id != ?"
                    f"{restriction_clause}{extra_clause} "
                    "LIMIT 25"
                )
                return conn.execute(
                    like_sql,
                    [f"%{like_term}%", norm_target, recipe_id] + restriction_params + extra_params,
                ).fetchall()

            without_target_rows = _fetch_similar(has_target=False, fts_q=fts_and_query)
            used_broad_search = False
            if len(without_target_rows) < 3 and fts_or_query != fts_and_query:
                broad_rows = _fetch_similar(has_target=False, fts_q=fts_or_query)
                if len(broad_rows) > len(without_target_rows):
                    without_target_rows = broad_rows
                    used_broad_search = True

            with_target_rows = _fetch_similar(has_target=True, fts_q=fts_and_query)

            # 6. Deduplicated ingredient frequencies in both groups
            freq_without: dict[str, int] = {}
            supporting_recipes: dict[str, list[dict[str, str]]] = {}
            for row in without_target_rows:
                rid = row["recipe_id"]
                ings = {
                    r["norm_name"]
                    for r in conn.execute(
                        "SELECT norm_name FROM recipe_ingredients WHERE recipe_id = ? AND norm_name != ''",
                        (rid,),
                    ).fetchall()
                }
                for ing_name in ings:
                    if ing_name != norm_target:
                        freq_without[ing_name] = freq_without.get(ing_name, 0) + 1
                        supporting_recipes.setdefault(ing_name, []).append(
                            {"recipe_id": rid, "title": row["title"]}
                        )

            freq_with: dict[str, int] = {}
            for row in with_target_rows:
                rid = row["recipe_id"]
                ings = {
                    r["norm_name"]
                    for r in conn.execute(
                        "SELECT norm_name FROM recipe_ingredients WHERE recipe_id = ? AND norm_name != ''",
                        (rid,),
                    ).fetchall()
                }
                for ing_name in ings:
                    if ing_name != norm_target:
                        freq_with[ing_name] = freq_with.get(ing_name, 0) + 1

            # 7. Candidates appearing in >= 2 similar recipes without target & not already in target
            candidates = [
                (ing, freq)
                for ing, freq in freq_without.items()
                if freq >= 2 and ing not in target_recipe_norm_ings
            ]
            # Prioritize ingredients more common WITHOUT target than WITH target
            n_without = max(len(without_target_rows), 1)
            n_with = max(len(with_target_rows), 1)
            candidates.sort(
                key=lambda x: (
                    -(x[1] / n_without - freq_with.get(x[0], 0) / n_with),
                    -x[1],
                )
            )

            def _evidence_strength(freq: int) -> str:
                if freq >= 3 and not used_broad_search:
                    return "strong"
                elif freq >= 2:
                    return "indirect"
                return "weak"

            substitution_candidates = [
                {
                    "substitute": ing,
                    "supporting_recipe_count": freq,
                    "count_in_similar_with_target": freq_with.get(ing, 0),
                    "evidence_strength": _evidence_strength(freq),
                    "supporting_recipe_ids": [s["recipe_id"] for s in supporting_recipes.get(ing, [])[:5]],
                    "supporting_recipes": supporting_recipes.get(ing, [])[:5],
                }
                for ing, freq in candidates[:15]
            ]

            if any(c["evidence_strength"] == "strong" for c in substitution_candidates):
                overall_strength = "strong"
            elif any(c["evidence_strength"] == "indirect" for c in substitution_candidates):
                overall_strength = "indirect"
            else:
                overall_strength = "weak"

            return {
                "target_recipe": {
                    "recipe_id": recipe_id,
                    "title": recipe_title,
                    "ingredients_raw": ingredients_raw,
                    "instructions_raw": recipe_row["instructions_raw"],
                },
                "target_ingredient_normalized": norm_target,
                "similar_without_target_count": len(without_target_rows),
                "similar_with_target_count": len(with_target_rows),
                "similar_without_target": [
                    {
                        "recipe_id": r["recipe_id"],
                        "title": r["title"],
                        "ingredients_snippet": json.loads(r["ingredients_raw"])[:8] if r["ingredients_raw"] else [],
                    }
                    for r in without_target_rows[:10]
                ],
                "substitution_candidates": substitution_candidates,
                "evidence_strength_overall": overall_strength,
                "evidence_type": "indirect (broadened title query)" if used_broad_search else "direct (same dish query)",
                "restrictions_applied": restrictions or [],
                "disclaimer": (
                    "Substitutions are based on recipe text analysis only and are not "
                    "medically certified for severe allergies or dietary conditions."
                ),
            }
        finally:
            conn.close()
    except Exception as e:
        logger.error("find_substitution_evidence error: %s", e)
        return {"error": str(e), "recipe_id_or_title": recipe_id_or_title}


# ---------------------------------------------------------------------------
# FUNCTION 5: web_search_fallback
# ---------------------------------------------------------------------------

def web_search_fallback(query: str) -> dict[str, Any]:
    """Secondary fallback search using DuckDuckGo when local evidence is weak."""
    try:
        from duckduckgo_search import DDGS

        results_raw = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results_raw.append(r)

        return {
            "source": "web_search",
            "query": query,
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "tag": f"[External Web Source: {r.get('href', '')}]",
                }
                for r in results_raw
            ],
            "warning": (
                "These results are from external web sources, not the local recipe dataset. "
                "Verify independently."
            ),
        }
    except Exception as e:
        logger.error("web_search_fallback error: %s", e)
        return {
            "source": "web_search",
            "error": str(e),
            "results": [],
        }
