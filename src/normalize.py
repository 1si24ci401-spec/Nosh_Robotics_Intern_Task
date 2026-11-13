"""
src/normalize.py
~~~~~~~~~~~~~~~~
Ingredient normalization and instruction step counting utilities for the
recipe chatbot pipeline.
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DAIRY_INGREDIENTS: set[str] = {
    "milk", "cream", "butter", "cheese", "yogurt", "whey", "ghee",
    "lactose", "casein", "cheddar", "mozzarella", "parmesan", "parmigiano",
    "parmigiano-reggiano", "pecorino", "pecorino romano", "romano", "asiago",
    "gruyere", "fontina", "gorgonzola", "burrata", "stracciatella", "feta",
    "ricotta", "brie", "gouda", "swiss", "provolone", "cream cheese",
    "sour cream", "heavy cream", "whipping cream", "half and half", "half-and-half",
    "buttermilk", "kefir", "ice cream", "gelato", "mascarpone", "creme fraiche",
    "halloumi", "paneer", "cotija", "queso", "queso fresco", "manchego",
    "camembert", "roquefort", "stilton", "emmental", "havarti", "monterey jack",
    "cottage cheese", "cheddar cheese", "ricotta cheese",
    "evaporated milk", "condensed milk", "sweetened condensed milk",
    "whole milk", "skim milk", "nonfat milk", "goat cheese",
}

# Non-dairy items that contain dairy-sounding words (milk, cream, butter)
NON_DAIRY_EXCEPTIONS: set[str] = {
    "coconut milk", "almond milk", "oat milk", "soy milk", "rice milk",
    "cashew milk", "hemp milk", "coconut cream", "cream of tartar",
    "peanut butter", "almond butter", "cashew butter", "sunflower butter",
    "cocoa butter", "shea butter", "apple butter", "pumpkin butter",
    "butternut", "butternut squash",
}

DIETARY_GROUPS: dict[str, set[str]] = {
    "dairy": DAIRY_INGREDIENTS,
    "gluten": {"flour", "wheat", "barley", "rye", "malt", "bread", "pasta", "noodle"},
    "nuts": {
        "almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut",
        "macadamia", "brazil nut", "pine nut", "peanut", "peanut butter",
    },
    "eggs": {"egg", "egg white", "egg yolk"},
    "egg": {"egg", "egg white", "egg yolk"},
    "peanut": {"peanut", "peanut butter", "peanut oil", "peanut sauce"},
    "peanuts": {"peanut", "peanut butter", "peanut oil", "peanut sauce"},
    "meat": {
        "chicken", "beef", "pork", "lamb", "turkey", "bacon", "ham",
        "sausage", "pepperoni", "salami", "prosciutto",
    },
    "shellfish": {"shrimp", "crab", "lobster", "clam", "oyster", "mussel", "scallop"},
    "fish": {"salmon", "tuna", "cod", "tilapia", "halibut", "anchovy", "sardine", "mackerel"},
}

# ---------------------------------------------------------------------------
# Internal lookup tables
# ---------------------------------------------------------------------------

# Phrases / multi-word canonical mappings (checked before single-word mapping)
_PHRASE_CANONICAL: dict[str, str] = {
    "garlic cloves": "garlic",
    "garlic clove": "garlic",
    "scallions": "green onion",
    "scallion": "green onion",
    "spring onion": "green onion",
    "spring onions": "green onion",
    "green onions": "green onion",
    "jalapeños": "jalapeño",
    "jalapenos": "jalapeño",
    "jalapeno": "jalapeño",
    "chiles": "chile",
    "chilis": "chile",
    "chilli": "chile",
    "chilies": "chile",
    "chickpeas": "chickpea",
    "garbanzo beans": "chickpea",
    "garbanzo bean": "chickpea",
    "heavy whipping cream": "heavy cream",
    "whipping cream": "heavy cream",
    "all purpose flour": "all-purpose flour",
    "parmesan cheese": "parmesan",
    "mozzarella cheese": "mozzarella",
    "feta cheese": "feta",
    "unsalted butter": "butter",
    "salted butter": "butter",
    "unsweetened cocoa powder": "cocoa powder",
    "semi-sweet chocolate chips": "chocolate chips",
    "ground cumin": "cumin",
    "ground coriander": "coriander",
    "ground cinnamon": "cinnamon",
    "ground turmeric": "turmeric",
    "ground ginger": "ginger",
    "chicken stock": "chicken broth",
    "beef stock": "beef broth",
    "vegetable stock": "vegetable broth",
    "confectioners sugar": "powdered sugar",
    "icing sugar": "powdered sugar",
    "egg whites": "egg white",
    "egg yolks": "egg yolk",
    "cherry tomatoes": "cherry tomato",
    "roma tomatoes": "roma tomato",
    "plum tomatoes": "plum tomato",
    "sun-dried tomatoes": "sun-dried tomato",
}

# Single-word canonical mappings
_WORD_CANONICAL: dict[str, str] = {
    "tomatoes": "tomato",
    "onions": "onion",
    "eggs": "egg",
    "potatoes": "potato",
    "carrots": "carrot",
    "peppers": "pepper",
    "mushrooms": "mushroom",
    "apples": "apple",
    "bananas": "banana",
    "oranges": "orange",
    "lemons": "lemon",
    "limes": "lime",
    "berries": "berry",
    "strawberries": "strawberry",
    "blueberries": "blueberry",
    "cherries": "cherry",
    "almonds": "almond",
    "walnuts": "walnut",
    "cashews": "cashew",
    "beans": "bean",
    "peas": "pea",
    "lentils": "lentil",
    "noodles": "noodle",
    "crackers": "cracker",
    "cookies": "cookie",
}

# Preserved phrases — these must never be altered by singularization or mapping
_PRESERVED: set[str] = {
    "coconut milk", "almond milk", "oat milk", "peanut butter", "almond butter",
    "cream cheese", "cottage cheese", "ricotta cheese", "cheddar cheese",
    "sour cream", "heavy cream", "tomato sauce", "tomato paste", "tomato puree",
    "olive oil", "vegetable oil", "sesame oil", "coconut oil", "canola oil",
    "soy sauce", "fish sauce", "worcestershire sauce", "hot sauce",
    "baking soda", "baking powder", "vanilla extract", "brown sugar",
    "powdered sugar", "black pepper", "white pepper", "red pepper flakes",
    "cayenne pepper", "chicken broth", "beef broth", "vegetable broth",
    "dark chocolate", "milk chocolate", "white chocolate", "chocolate chips",
    "bread flour", "cake flour", "whole wheat flour", "all-purpose flour",
    "egg white", "egg yolk",
}

# Unit tokens to remove
_UNITS: set[str] = {
    "tablespoon", "tablespoons", "tbsp",
    "teaspoon", "teaspoons", "tsp",
    "cup", "cups",
    "ounce", "ounces", "oz",
    "pound", "pounds", "lb", "lbs",
    "gram", "grams", "g",
    "kilogram", "kilograms", "kg",
    "liter", "liters", "ml",
    "clove", "cloves",
    "can", "cans",
    "package", "packages", "pkg", "pkgs",
    "slice", "slices",
    "piece", "pieces",
    "sprig", "sprigs",
    "stalk", "stalks",
    "bunch", "bunches",
    "head", "heads",
    "drop", "drops",
    "pinch", "pinches",
    "dash", "dashes",
    "handful", "handfuls",
    "stick", "sticks",
    "jar", "jars",
    "bag", "bags",
    "box", "boxes",
    "quart", "quarts", "pint", "pints",
}

# Prep adjectives / modifiers to remove
_PREP_ADJECTIVES: set[str] = {
    "finely", "coarsely", "thinly", "thickly", "lightly", "freshly",
    "diced", "minced", "chopped", "sliced", "crushed", "melted",
    "fresh", "ground", "shredded", "grated", "peeled", "seeded",
    "pitted", "halved", "quartered", "whole", "raw", "cooked",
    "frozen", "thawed", "drained", "rinsed", "sifted", "softened",
    "cold", "warm", "hot", "beaten", "whipped", "toasted", "roasted",
    "smoked", "dried", "canned", "packed", "heaping", "level",
    "scant", "generous", "large", "medium", "small", "extra",
    "optional", "divided", "separated", "inch", "inches", "advertisement",
}

# Multi-word prep phrases to strip (processed before token removal)
_PREP_PHRASES: tuple[str, ...] = (
    "to taste", "if desired", "as needed", "for serving", "for garnish",
    "at room temperature", "room temperature",
)

# Unicode fraction -> ASCII mapping
_UNICODE_FRACTIONS: dict[str, str] = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}

# Conservative singularization: words > 4 chars ending in 's' (not these suffixes)
_SING_SKIP_SUFFIXES: tuple[str, ...] = ("ss", "us", "ous", "ias", "eas", "ness")

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

_RE_PAREN = re.compile(r"\([^)]*\)")
_RE_MIXED_FRACTION = re.compile(r"\b(\d+)\s+(\d+/\d+)\b")
_RE_FRACTION = re.compile(r"\b\d+/\d+\b")
_RE_DECIMAL = re.compile(r"\b\d+(?:\.\d+)?\b")
_RE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_RE_PUNCT = re.compile(r"[,;:.]")


def _normalize_unicode_fractions(text: str) -> str:
    """Replace unicode fraction characters with ASCII equivalents."""
    for uc, asc in _UNICODE_FRACTIONS.items():
        text = text.replace(uc, f" {asc} ")
    return text


def _extract_quantity(text: str) -> tuple[str, Optional[str]]:
    """
    Extract the first quantity token from *text* (after unicode normalization).
    Returns (text_with_all_numbers_removed, quantity_string_or_None).
    """
    m = _RE_MIXED_FRACTION.search(text)
    if m:
        quantity = m.group(0).strip()
        text = _RE_MIXED_FRACTION.sub(" ", text)
        text = _RE_FRACTION.sub(" ", text)
        text = _RE_DECIMAL.sub(" ", text)
        return text, quantity

    m = _RE_FRACTION.search(text)
    if m:
        quantity = m.group(0)
        text = _RE_FRACTION.sub(" ", text)
        text = _RE_DECIMAL.sub(" ", text)
        return text, quantity

    m = _RE_DECIMAL.search(text)
    if m:
        quantity = m.group(0)
        text = _RE_DECIMAL.sub(" ", text)
        return text, quantity

    return text, None


def _remove_tokens(text: str, token_set: set[str]) -> str:
    """Remove whole-word tokens that appear in *token_set* (case-insensitive)."""
    words = text.split()
    return " ".join(w for w in words if w.lower().strip(",;.") not in token_set)


def _remove_prep_phrases(text: str) -> str:
    """Strip multi-word prep phrases from text."""
    for phrase in _PREP_PHRASES:
        text = text.replace(phrase, " ")
    return text


def _apply_phrase_canonical(text: str) -> str:
    """Apply multi-word canonical mappings, longest first."""
    for phrase, canon in sorted(_PHRASE_CANONICAL.items(), key=lambda x: -len(x[0])):
        if phrase in text:
            text = re.sub(rf"\b{re.escape(phrase)}\b", canon, text)
    return text


def _apply_word_canonical(text: str) -> str:
    """Apply single-word canonical mappings."""
    words = text.split()
    return " ".join(_WORD_CANONICAL.get(w, w) for w in words)


def _conservative_singularize(text: str) -> str:
    """
    Strip trailing 's' from words > 4 chars ending in 's', unless:
    - word ends in a skip suffix (ss, us, ous, ias, eas, ness)
    """
    words = text.split()
    result: list[str] = []
    for word in words:
        if (
            len(word) > 4
            and word.endswith("s")
            and not any(word.endswith(suf) for suf in _SING_SKIP_SUFFIXES)
        ):
            result.append(word[:-1])
        else:
            result.append(word)
    return " ".join(result)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_ingredient(raw: str) -> tuple[str, Optional[str], Optional[str]]:
    """
    Normalize a raw ingredient string.

    Parameters
    ----------
    raw:
        Raw ingredient text, e.g. ``"2 cups diced tomatoes (canned)"``.

    Returns
    -------
    tuple of (norm_name, quantity, unit)
        *norm_name* - canonical ingredient name, lowercased.
        *quantity*  - extracted quantity string, or None.
        *unit*      - extracted unit string, or None.
    """
    if not raw or not raw.strip():
        return ("", None, None)

    text = raw.strip()

    # 1. Strip dataset artifacts (e.g., AllRecipes "ADVERTISEMENT") & parenthetical notes
    text = re.sub(r"\bADVERTISEMENT\b", " ", text, flags=re.IGNORECASE)
    text = _RE_PAREN.sub(" ", text)

    # Lowercase early so all subsequent lookups are case-insensitive
    text = text.lower()

    # Normalize unicode fractions and strip dimension phrases like "1/4-inch"
    text = _normalize_unicode_fractions(text)
    text = re.sub(r"\b\d+(?:/\d+)?-?inch(?:es)?\b", " ", text)
    text = re.sub(r"-inch(?:es)?\b", " ", text)

    # 2. Extract quantity (and strip all numeric tokens)
    text, quantity = _extract_quantity(text)

    # Identify unit: first remaining token that is a known unit
    words = text.split()
    unit: Optional[str] = None
    for w in words:
        clean_w = _RE_PUNCT.sub("", w)
        if clean_w in _UNITS:
            unit = clean_w
            break

    # 3 & 4. Remove unit tokens
    text = _remove_tokens(text, _UNITS)

    # 5a. Remove multi-word prep phrases
    text = _remove_prep_phrases(text)

    # 5b. Remove single-word prep adjectives
    text = _remove_tokens(text, _PREP_ADJECTIVES)

    # 6. Remove punctuation and standalone hyphens
    text = _RE_PUNCT.sub(" ", text)
    text = re.sub(r"(?:^|\s)-+(?:\s|$)", " ", text)

    # Collapse whitespace
    text = " ".join(text.split())

    # 7. Apply canonical mappings — check preserve list first
    if text in _PRESERVED:
        return (text, quantity, unit)

    text = _apply_phrase_canonical(text)
    if text in _PRESERVED:
        return (text, quantity, unit)

    text = _apply_word_canonical(text)
    if text in _PRESERVED:
        return (text, quantity, unit)

    # 8. Conservative singularization (only if not in preserve list already)
    text = _conservative_singularize(text)
    if text in _PRESERVED:
        return (text, quantity, unit)

    # 9. Final lowercase + strip
    text = text.lower().strip()

    return (text, quantity, unit)


def count_steps(instructions: str) -> int:
    """
    Count the number of meaningful steps in a recipe instructions string.

    Rule: Split on newlines and sentence boundaries ([.!?]\\s+), then keep
    fragments >= 4 characters containing at least one ASCII letter.

    Returns 0 for empty instructions, or >= 1 for non-empty instructions.
    """
    if not instructions or not instructions.strip():
        return 0

    lines = instructions.splitlines()

    fragments: list[str] = []
    for line in lines:
        sentences = _RE_SENTENCE_SPLIT.split(line)
        fragments.extend(sentences)

    meaningful = [
        f for f in fragments
        if len(f.strip()) >= 4 and re.search(r"[a-zA-Z]", f)
    ]

    return max(len(meaningful), 1)
