import json, logging, os, time
from dataclasses import dataclass, field
from typing import Any, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types
from src import tools
from src.normalize import DIETARY_GROUPS


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    last_query: Optional[str] = None
    pantry_ingredients: list[str] = field(default_factory=list)
    include_ingredients: list[str] = field(default_factory=list)
    exclude_ingredients: list[str] = field(default_factory=list)
    max_steps: Optional[int] = None
    active_recipe_id: Optional[str] = None
    last_shown_recipe_ids: list[str] = field(default_factory=list)
    conversation_history: list[dict] = field(default_factory=list)  # for display only

    def reset(self):
        self.last_query = None
        self.pantry_ingredients.clear()
        self.include_ingredients.clear()
        self.exclude_ingredients.clear()
        self.max_steps = None
        self.active_recipe_id = None
        self.last_shown_recipe_ids.clear()
        self.conversation_history.clear()

    def to_summary(self) -> str:
        parts = []
        if self.last_query:
            parts.append(f"Last search query: {self.last_query!r}")
        if self.pantry_ingredients:
            parts.append(f"Pantry ingredients: {', '.join(self.pantry_ingredients)}")
        if self.include_ingredients:
            parts.append(f"Required ingredients: {', '.join(self.include_ingredients)}")
        if self.exclude_ingredients:
            parts.append(f"Excluded ingredients/groups: {', '.join(self.exclude_ingredients)}")
        if self.max_steps is not None:
            parts.append(f"Max steps: {self.max_steps}")
        if self.active_recipe_id:
            parts.append(f"Active recipe: {self.active_recipe_id}")
        if self.last_shown_recipe_ids:
            ids_str = ", ".join(f"#{i+1}={rid}" for i, rid in enumerate(self.last_shown_recipe_ids[:5]))
            parts.append(f"Last shown recipes: {ids_str}")
        return "; ".join(parts) if parts else "No active filters."


# ---------------------------------------------------------------------------
# Tool declarations
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="search_recipes",
        description="Search the recipe database using a text query and/or ingredient filters. Returns matching recipes with IDs, titles, ingredients, and instructions. Use for: finding recipes by dish name, ingredient, cuisine; applying dietary restrictions; browsing the dataset.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(
                    type=types.Type.STRING,
                    description="Natural language search query (dish name, cuisine, description). Leave empty to filter by ingredients only.",
                ),
                "include_ingredients": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Ingredients that MUST appear in results.",
                ),
                "exclude_ingredients": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Ingredients or dietary group names (e.g. 'dairy', 'gluten', 'nuts') to EXCLUDE from results.",
                ),
                "max_steps": types.Schema(
                    type=types.Type.INTEGER,
                    description="Maximum number of instruction steps allowed.",
                ),
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of results to return (default 10).",
                ),
            },
            required=[],
        ),
    ),
    types.FunctionDeclaration(
        name="compute_dataset_stats",
        description="Compute exact statistics over the recipe dataset. Use for: counting recipes with specific ingredients, computing percentages, finding most common ingredients, average ingredient counts, ranking recipes by step count.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "stat_type": types.Schema(
                    type=types.Type.STRING,
                    description="One of: 'count' (count + percentage), 'common_ingredients' (top-N frequent ingredients), 'avg_ingredients' (average/median ingredient count), 'fewest_steps' (rank by fewest steps), 'most_steps' (rank by most steps).",
                ),
                "include_ingredients": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Filter: recipes must contain these ingredients.",
                ),
                "exclude_ingredients": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Filter: recipes must NOT contain these ingredients.",
                ),
                "group_by": types.Schema(
                    type=types.Type.STRING,
                    description="Optional grouping field (e.g. 'source').",
                ),
                "top_n": types.Schema(
                    type=types.Type.INTEGER,
                    description="For ranked results, how many to return (default 10).",
                ),
            },
            required=["stat_type"],
        ),
    ),
    types.FunctionDeclaration(
        name="match_pantry_recipes",
        description="Given available pantry ingredients, find and rank the best matching recipes using a deterministic scoring formula. Hard constraints (exclusions, max steps) are NEVER relaxed. Use for: 'I have X, Y, Z — what can I make?'",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "available_ingredients": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="List of ingredients the user has available.",
                ),
                "exclude_ingredients": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Hard exclusions: ingredient names or dietary group names.",
                ),
                "max_steps": types.Schema(
                    type=types.Type.INTEGER,
                    description="Hard constraint: maximum instruction steps.",
                ),
                "prefer_fewer_steps": types.Schema(
                    type=types.Type.BOOLEAN,
                    description="Prefer recipes with fewer steps as a tiebreaker.",
                ),
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of top results to return (default 5).",
                ),
            },
            required=["available_ingredients"],
        ),
    ),
    types.FunctionDeclaration(
        name="find_substitution_evidence",
        description="Find evidence-based ingredient substitutions for a recipe by mining the local dataset. Returns supporting recipe IDs, evidence strength, and substitution candidates. Use for: 'Remove eggs from banana bread', 'Replace cream without dairy'.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "recipe_id_or_title": types.Schema(
                    type=types.Type.STRING,
                    description="Recipe ID or title to adapt.",
                ),
                "target_ingredient": types.Schema(
                    type=types.Type.STRING,
                    description="The ingredient to substitute or remove.",
                ),
                "restrictions": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description="Hard restrictions the substitute must satisfy (e.g. 'no dairy', 'no nuts').",
                ),
            },
            required=["recipe_id_or_title", "target_ingredient"],
        ),
    ),
    types.FunctionDeclaration(
        name="web_search_fallback",
        description="Search the web for ingredient substitution information. USE ONLY as a secondary fallback when local dataset evidence is weak or inadequate. Results are clearly tagged as external sources.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(
                    type=types.Type.STRING,
                    description="Search query for ingredient substitution.",
                ),
            },
            required=["query"],
        ),
    ),
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

TOOL_DISPATCHER = {
    "search_recipes": tools.search_recipes,
    "compute_dataset_stats": tools.compute_dataset_stats,
    "match_pantry_recipes": tools.match_pantry_recipes,
    "find_substitution_evidence": tools.find_substitution_evidence,
    "web_search_fallback": tools.web_search_fallback,
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a recipe assistant chatbot backed by a local SQLite database of the Eight Portions Recipe Box dataset (~125,000 recipes across AllRecipes, Epicurious, and Food Network).

CRITICAL RULES — NEVER VIOLATE:
1. NEVER guess counts, percentages, rankings, or recipe IDs. ALWAYS call a tool to get this data.
2. NEVER invent recipe content, ingredients, or instructions not found in tool results.
3. NEVER fabricate unavailable attributes such as nutrition values, calorie counts, or missing cooking/prep times — state clearly what is missing from the dataset.
4. For ANY factual claim about recipes (counts, rankings, ingredients), call compute_dataset_stats or search_recipes first.
5. Hard constraints (exclude_ingredients, max_steps) are ABSOLUTE — never silently relax them. If match_pantry_recipes returns eligible_recipes=[], state clearly that NO eligible match was found, and present closest_violating_alternatives separately with their explicit violated_constraints.
6. If dataset evidence is weak for substitutions, state the uncertainty explicitly before calling web_search_fallback, and tag any external web info with [External Web Source: <url>].

BEHAVIOR RULES:
- Maintain context across turns:
  * If user adds a dietary restriction ("I cannot have dairy", "Exclude eggs too"), combine it with SESSION STATE's existing query/pantry/exclusions and re-run the relevant tool!
  * When user refers to "this recipe", "the second one", or "the pasta recipe", resolve the recipe_id from SESSION STATE.
- Always show recipe_ids in responses so users can reference them.
- For statistical questions: always show numerator, denominator, percentage, filters applied, and explain ingredient-name normalization.
- For pantry matching: show matched ingredients, missing/extra required ingredients, step counts, score formula breakdown, and explicitly state quantity sufficiency was not verified when applicable.
- For substitutions: output (1) supporting local recipe_id citations (and whether evidence is direct or indirect), (2) full Updated Ingredient List, (3) full Revised Step-by-Step Instructions, (4) Predicted Effects vs. Verified Outcomes (flavor, moisture, binding, texture), and (5) an explicit disclaimer that substitutions are based on recipe text only and not medically certified for severe allergies.

TOOL USAGE GUIDE:
- search_recipes: Finding recipes, applying dietary filters, browsing by dish/ingredient
- compute_dataset_stats: ANY count, percentage, common ingredients, average/median, or step-count ranking
- match_pantry_recipes: Matching recipes to a user's pantry ingredients + constraints
- find_substitution_evidence: Mining local dataset evidence for replacing/removing an ingredient
- web_search_fallback: Secondary fallback ONLY when find_substitution_evidence has weak/inadequate local evidence
"""


# ---------------------------------------------------------------------------
# RecipeAgent
# ---------------------------------------------------------------------------

DEFAULT_FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
]


class RecipeAgent:
    def __init__(self, api_key: Optional[str] = None):
        load_dotenv()
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY not set. Copy .env.example to .env and add your key.")
        self.client = genai.Client(api_key=key)
        self.model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.state = SessionState()
        self.gemini_history: list[types.Content] = []  # Gemini conversation history
        self._tool = types.Tool(function_declarations=TOOL_DECLARATIONS)
        self._system_prompt = SYSTEM_PROMPT

    def _call_model_with_fallback(self):
        """Call Gemini generate_content, falling back across Flash models on 503/404."""
        candidates = [self.model] + [m for m in DEFAULT_FALLBACK_MODELS if m != self.model]
        last_err: Optional[Exception] = None
        for model_name in candidates:
            for attempt in range(2):
                try:
                    resp = self.client.models.generate_content(
                        model=model_name,
                        contents=self.gemini_history,
                        config=types.GenerateContentConfig(
                            system_instruction=self._system_prompt,
                            tools=[self._tool],
                            temperature=0.1,
                        ),
                    )
                    self.model = model_name
                    return resp
                except Exception as exc:
                    last_err = exc
                    msg = str(exc)
                    if "503" in msg or "UNAVAILABLE" in msg or "429" in msg:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    if "404" in msg or "NOT_FOUND" in msg:
                        break
                    raise
        raise last_err if last_err is not None else RuntimeError("All Gemini models failed.")

    def chat(self, user_message: str) -> str:
        """Process one user turn and return the agent's response string."""
        # 1. Build the user message with state context injected
        state_context = f"\n\n[SESSION STATE: {self.state.to_summary()}]"
        full_user_message = user_message + state_context

        # 2. Add to Gemini history
        self.gemini_history.append(types.Content(
            role="user",
            parts=[types.Part(text=full_user_message)]
        ))

        # 3. Agentic loop: call Gemini, handle function calls, repeat until text response
        max_iterations = 10
        for iteration in range(max_iterations):
            response = self._call_model_with_fallback()

            if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                return "I could not generate a response for that request. Please try rephrasing."

            candidate = response.candidates[0]

            # Check for function calls
            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if part.function_call is not None
            ]

            if not function_calls:
                # Text response — we're done
                self.gemini_history.append(candidate.content)
                text = "".join(
                    part.text for part in candidate.content.parts if hasattr(part, "text") and part.text
                )
                # Update session state from the response (parse any state updates)
                self._update_state_from_response(response, user_message)
                self.state.conversation_history.append({"role": "assistant", "content": text})
                return text

            # Execute function calls
            self.gemini_history.append(candidate.content)
            function_response_parts = []
            for fc in function_calls:
                result = self._execute_tool(fc.name, dict(fc.args))
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": result},
                    )
                )
                # Update state from tool calls
                self._update_state_from_tool(fc.name, dict(fc.args), result)

            self.gemini_history.append(
                types.Content(role="user", parts=function_response_parts)
            )

        return "I encountered an issue processing your request. Please try rephrasing."

    def _execute_tool(self, name: str, args: dict) -> dict:
        """Execute a tool by name with given args. Returns result dict."""
        fn = TOOL_DISPATCHER.get(name)
        if fn is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return fn(**args)
        except Exception as e:
            logging.error(f"Tool {name} failed: {e}", exc_info=True)
            return {"error": str(e), "tool": name}

    def _update_state_from_tool(self, tool_name: str, args: dict, result: dict):
        """Update SessionState based on tool calls and results."""
        if tool_name == "search_recipes":
            if args.get("query"):
                self.state.last_query = args["query"]
            if "results" in result:
                self.state.last_shown_recipe_ids = [r["recipe_id"] for r in result["results"][:10]]
                if result["results"]:
                    self.state.active_recipe_id = result["results"][0]["recipe_id"]
            if args.get("exclude_ingredients"):
                for exc in args["exclude_ingredients"]:
                    if exc not in self.state.exclude_ingredients:
                        self.state.exclude_ingredients.append(exc)
            if args.get("include_ingredients"):
                self.state.include_ingredients = list(args["include_ingredients"])
            if args.get("max_steps") is not None:
                self.state.max_steps = args["max_steps"]
        elif tool_name == "match_pantry_recipes":
            if args.get("available_ingredients"):
                self.state.pantry_ingredients = list(args["available_ingredients"])
            if result.get("eligible_recipes"):
                self.state.last_shown_recipe_ids = [r["recipe_id"] for r in result["eligible_recipes"]]
                self.state.active_recipe_id = result["eligible_recipes"][0]["recipe_id"]
            if args.get("exclude_ingredients"):
                for exc in args["exclude_ingredients"]:
                    if exc not in self.state.exclude_ingredients:
                        self.state.exclude_ingredients.append(exc)
            if args.get("max_steps") is not None:
                self.state.max_steps = args["max_steps"]
        elif tool_name == "find_substitution_evidence":
            if result.get("target_recipe", {}).get("recipe_id"):
                self.state.active_recipe_id = result["target_recipe"]["recipe_id"]

    def _update_state_from_response(self, response, user_message: str):
        """Parse user message for explicit state changes (simple keyword matching)."""
        msg_lower = user_message.lower()
        # Detect explicit "no dairy", "no gluten", etc.
        for group_name in DIETARY_GROUPS:
            if (
                f"no {group_name}" in msg_lower
                or f"without {group_name}" in msg_lower
                or f"cannot have {group_name}" in msg_lower
                or f"can't have {group_name}" in msg_lower
            ):
                if group_name not in self.state.exclude_ingredients:
                    self.state.exclude_ingredients.append(group_name)
        # Detect explicit "exclude X" or "without X"
        # This is a simple heuristic; the LLM handles the main intent parsing

    def reset(self):
        self.state.reset()
        self.gemini_history.clear()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_agent(api_key: Optional[str] = None) -> RecipeAgent:
    """Factory function to create a RecipeAgent instance."""
    return RecipeAgent(api_key=api_key)
