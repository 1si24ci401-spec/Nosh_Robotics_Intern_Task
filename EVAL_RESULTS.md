# Evaluation Results — Nosh Robotics Recipe Assistant

Generated: 2026-11-13 10:01:11

---

## Summary

| Test | Status | Time (s) |
|------|--------|----------|
| 01_multiturn_search_dairy | ✅ PASS | 10.9 |
| 02_aggregate_stats | ✅ PASS | 0.66 |
| 03_pantry_matching | ✅ PASS | 17.49 |
| 04_no_match_edge_case | ✅ PASS | 4.28 |
| 05_substitution_evidence | ✅ PASS | 11.11 |
| 06_llm_comparison | ✅ PASS | 2.38 |

---

## 01_multiturn_search_dairy

```json
{
  "test": "01_multiturn_search_dairy",
  "turn_1_query": "Find me a penne pasta recipe",
  "turn_1_response": "Here are a few penne pasta recipes from the collection:\n\n1. **Penne Pasta Salad with Sun Dried Tomatoes, Asparagus and Basil** (Recipe ID: `fn_e90f1efb41ff60b9`)\n   - **Ingredients:** Penne pasta, fresh asparagus tips, garlic cloves, olive oil, salt and pepper, fresh basil, sun-dried tomatoes in oil.\n   - **Instructions:** Cook and drain pasta. Saut\u00e9 asparagus tips in garlic, olive oil, salt, and pepper until tender. Add to the pasta along with basil and sun-dried tomatoes, toss to mix, adjust seasonings, and refrigerate 1 hour or longer before serving.\n   - **Steps:** 7\n\n2. **Tuna Alfredo with Penne Pasta** (Recipe ID: `ar_c3305a289a2d4b38`)\n   - **Ingredients:** Penne pasta, tuna, onion powder, salt, Alfredo sauce, grated Parmesan cheese.\n   - **Instructions:** Boil penne until tender yet firm, then drain. Cook tuna in a skillet over low heat with onion powder and salt, stir into the pasta with Alfredo sauce, and garnish with Parmesan cheese.\n   - **Steps:** 7\n\n3. **Creamy Ham and Penne Pasta** (Recipe id: `fn_3052ae8876226754`)\n   - **Ingredients:** Dry penne pasta, frozen green peas, Ro*Tel\u00ae Mild Diced Tomatoes & Green Chilies, 1/3 less fat cream cheese (Neufchatel), shredded sharp Cheddar cheese, chopped fully cooked lean ham.\n   - **Instructions:** Cook pasta according to package directions, adding peas during the last 2 minutes, then drain. In the pasta pan, combine remaining ingredients and cook/stir over medium heat until cheese melts and is bubbly, then stir in the pasta and peas.\n   - **Steps:** 5\n\n4. **Penne Pasta with Cannellini Beans and Escarole** (Recipe ID: `ar_798ea03c686839a7`)\n   - **Ingredients:** Dry penne pasta, escarole, cannellini beans, diced tomatoes with garlic and onion, salt, ground black pepper.\n   - **Instructions:** Boil and drain penne. In a skillet over medium heat, cook and stir escarole, cannellini beans (with liquid), and diced tomatoes until heated through, season with salt and pepper, and toss with the pasta.\n   - **Steps:** 4\n\n5. **Penne Pesto Pasta Salad** (Recipe ID: `ar_aa48ecce16b653f1`)\n   - **Ingredients:** truRoots\u00ae Ancient Grains Organic Penne, prepared fresh basil pesto, mozzarella pearls, grape or cherry tomatoes, grated Parmesan cheese, sliced black olives, fresh basil sprigs (optional).\n   - **Instructions:** Cook pasta until al dente and drain. Combine pasta and pesto in a large bowl, stir in mozzarella, tomatoes, Parmesan, and olives, and chill until ready to serve.\n   - **Steps:** 6\n\n*(Note: Cooking times, prep times, and nutritional/calorie values are not provided as they are not available in the dataset.)* \n\nWould you like to refine this search with dietary restrictions, or modify any of these recipes?",
  "turn_2_query": "I cannot have dairy",
  "turn_2_response": "Here are dairy-free penne pasta recipes:\n\n1. **Penne with Edible Flowers** (Recipe ID: `fn_d9b9eaa5f4d22db0`)\n   - **Ingredients:** Penne, olive oil, garlic, sun-dried tomatoes, parsley, chives, chive blossoms, assorted edible flowers (e.g., nasturtiums, pansies, dandelions).\n   - **Instructions:** Boil pasta until al dente. While pasta cooks, heat oil in a skillet and cook garlic for 1 minute. Drain pasta, toss with warm garlic and oil, tomatoes, parsley, chives, and chopped flowers, and garnish with whole flowers.\n   - **Steps:** 6\n\n2. **Jalapeno Chermoula Penne and Flaked Fish** (Recipe ID: `fn_bd3a6ac051d32901`)\n   - **Ingredients:** Fresh basil, fresh cilantro, fresh mint, jalapeno peppers, garlic, shallot, lime juice, extra-virgin olive oil, salt and pepper, cod or flaky white fish, seafood seasoning, penne, toasted slivered almonds.\n   - **Instructions:** Pulse herbs, aromatics, lime juice, and olive oil in a food processor for the sauce. Broil seasoned fish until opaque. Boil penne to al dente (reserving 1 cup starchy water). Toss pasta with half the water, sauce, and half the flaked fish, then top with remaining fish and almonds.\n   - **Steps:** 10\n\n3. **Asparagus Lemon Pasta Salad** (Recipe ID: `fn_c4061b149e5c7e7f`)\n   - **Ingredients:** Penne, olive oil, asparagus, water, lemon juice, grated lemon rind, salt, pepper, jarred red pepper, pine nuts.\n   - **Instructions:** Prepare penne, toss with 1 tsp olive oil, and chill. Simmer asparagus pieces in water until tender, drain, and plunge into ice water. Toast pine nuts. Whisk lemon juice, zest, salt, pepper, and remaining olive oil in a large bowl, then add asparagus, drained red pepper, pine nuts, and pasta to serve.\n   - **Steps:** 12\n\n4. **Sweet Peppers with Pasta** (Recipe ID: `epi_54d2c0600882b461`)\n   - **Ingredients:** Large garlic cloves, extra-virgin olive oil, red and yellow bell peppers, dry white wine, penne, salt and pepper.\n   - **Instructions:** Cook garlic in oil in a skillet until golden. Add peppers, wine, salt, and pepper, and cook covered until very tender (15\u201320 minutes). Meanwhile, boil and drain penne, then toss with the pepper mixture.\n   - **Steps:** 10\n\n*(Note: Cooking times, prep times, and nutritional/calorie values are not provided as they are not available in the dataset.)*",
  "state_after": "Last search query: 'penne pasta'; Required ingredients: penne; Excluded ingredients/groups: dairy, milk, cheese, butter, cream, alfredo, mozzarella, parmesan, neufchatel, cheddar; Active recipe: fn_d9b9eaa5f4d22db0; Last shown recipes: #1=fn_d9b9eaa5f4d22db0, #2=fn_e03510d214593842, #3=fn_bd3a6ac051d32901, #4=fn_c4061b149e5c7e7f, #5=epi_54d2c0600882b461",
  "excluded_ingredients": [
    "parmesan",
    "butter",
    "alfredo",
    "cream",
    "cheese",
    "cheddar",
    "mozzarella",
    "milk",
    "dairy",
    "neufchatel"
  ],
  "passed": true,
  "elapsed_seconds": 10.9
}
```

## 02_aggregate_stats

```json
{
  "test": "02_aggregate_stats",
  "garlic_onion_count": {
    "stat_type": "count",
    "numerator": 7637,
    "denominator": 124483,
    "percentage": 6.13,
    "filters_applied": {
      "include_ingredients": [
        "garlic",
        "onion"
      ],
      "include_normalized": [
        "garlic",
        "onion"
      ],
      "exclude_ingredients": [],
      "expanded_exclusions": [],
      "group_by": null
    },
    "total_recipes_in_dataset": 124483,
    "normalization_note": "Ingredient names normalized via normalize_ingredient() (strips quantities, units, prep adjectives, parentheticals, and maps plurals/aliases such as tomatoes->tomato, garlic cloves->garlic, onions->onion)."
  },
  "tomato_fewest_steps": {
    "stat_type": "fewest_steps",
    "results": [
      {
        "rank": 1,
        "recipe_id": "ar_21acb6a7461b41e8",
        "title": "Black Bean and White Corn Salad",
        "step_count": 1,
        "instructions_snippet": "Mix white corn, black beans, tomatoes, red bell pepper, red onion, cilantro, lime juice, tequila, salt, and black pepper in a large salad bowl.\n"
      },
      {
        "rank": 2,
        "recipe_id": "ar_27d7046178a5b105",
        "title": "Summertime Tomato Salad",
        "step_count": 1,
        "instructions_snippet": "Whisk together the vegetable oil, vinegar, sugar, pepper, mustard, and seasoned salt in a bowl; add the tomato and onion to the bowl and toss to coat; cover and refrigerate overnight.\n"
      },
      {
        "rank": 3,
        "recipe_id": "ar_39cd7b77e94945cd",
        "title": "Refreshing Mango Chutney",
        "step_count": 1,
        "instructions_snippet": "Mix red onion, mango, tomato, and cilantro together in a bowl.\n"
      },
      {
        "rank": 4,
        "recipe_id": "ar_3f45b3e546e8d4e5",
        "title": "Vegetable and Fruit Juice",
        "step_count": 1,
        "instructions_snippet": "Juice carrots, tomato, strawberries, lime slices, ginger, apple, and red bell pepper using a juicer following manufacturer's instructions.\n"
      },
      {
        "rank": 5,
        "recipe_id": "ar_af7d5a4167ad528e",
        "title": "Easy Brunswick Stew",
        "step_count": 1,
        "instructions_snippet": "Combine cream-style corn, diced tomatoes, chicken, pork, sweet corn, ketchup, tomato sauce, water, bacon drippings, barbeque sauce, Worcestershire sauce, hot sauce, and black pepper together in a Dutc"
      }
    ],
    "total_recipes_analyzed": 4426,
    "total_recipes_in_dataset": 124483,
    "step_counting_rule": "Split instructions on newlines and sentence boundaries ([.!?]\\s+); count fragments >= 4 chars containing at least one ASCII letter.",
    "normalization_note": "Ingredient names normalized via normalize_ingredient() (strips quantities, units, prep adjectives, parentheticals, and maps plurals/aliases such as tomatoes->tomato, garlic cloves->garlic, onions->onion).",
    "filters_applied": {
      "include_ingredients": [
        "tomato"
      ],
      "include_normalized": [
        "tomato"
      ],
      "exclude_ingredients": [],
      "expanded_exclusions": [],
      "group_by": null
    }
  },
  "passed": true,
  "elapsed_seconds": 0.66
}
```

## 03_pantry_matching

```json
{
  "test": "03_pantry_matching",
  "turn_1_response": "Based on your pantry ingredients (**eggs, onions, tomatoes, and rice**) and constraints (**no peanuts, at most 6 instruction steps**), here are the top 5 matching recipes from our database. \n\n*Note: Quantity sufficiency was not verified (name-level match only; recipe units/yields vary across sources and cannot be reliably compared).*\n\n---\n\n### 1. **QA** (Recipe ID: `fn_20785db8d9cf36ce`)\n* **Score:** 1.85 *(Score formula: `2.0 * matched - 1.0 * extra_required - 0.15 * step_count`)*\n* **Step Count:** 1 step\n* **Matched Pantry Ingredients:** `rice`\n* **Extra / Missing Required Ingredients:** None\n* **Unused Pantry Ingredients:** `eggs`, `onions`, `tomatoes`\n\n---\n\n### 2. **Tst** (Recipe ID: `fn_0768e679c73db70e`)\n* **Score:** 2.4\n* **Step Count:** 4 steps\n* **Matched Pantry Ingredients:** `onions`, `tomatoes`\n* **Extra Required Ingredients (Missing from pantry):** `grreen chillie`\n* **Unused Pantry Ingredients:** `eggs`, `rice`\n\n---\n\n### 3. **Tstcgdgdgdgdgdgdgd** (Recipe ID: `fn_0ba6bc0a49c4f0aa`)\n* **Score:** 2.4\n* **Step Count:** 4 steps\n* **Matched Pantry Ingredients:** `onions`, `tomatoes`\n* **Extra Required Ingredients (Missing from pantry):** `grreen chillie`\n* **Unused Pantry Ingredients:** `eggs`, `rice`\n\n---\n\n### 4. **Western Denver** (Recipe ID: `ar_f3f170fcc0bdcc0f`)\n* **Score:** 1.55\n* **Step Count:** 3 steps\n* **Matched Pantry Ingredients:** `eggs`, `onions`\n* **Extra Required Ingredients (Missing from pantry):** `green bell pepper`, `red bell pepper`\n* **Unused Pantry Ingredients:** `rice`, `tomatoes`\n\n---\n\n### 5. **Grilled Onions** (Recipe ID: `fn_61c77fd69c2f7cfa`)\n* **Score:** 1.55\n* **Step Count:** 3 steps\n* **Matched Pantry Ingredients:** `onions`\n* **Extra Required Ingredients (Missing from pantry):** None\n* **Unused Pantry Ingredients:** `eggs`, `rice`, `tomatoes`",
  "turn_2_response": "With **eggs** now excluded in addition to peanuts (while keeping your pantry items as onions, tomatoes, and rice, and a maximum of 6 steps), here are the top 5 matching recipes:\n\n*Note: Quantity sufficiency was not verified (name-level match only; recipe units/yields vary across sources and cannot be reliably compared).*\n\n---\n\n### 1. **Tst** (Recipe ID: `fn_0768e679c73db70e`)\n* **Score:** 2.4 *(Score formula: `2.0 * matched - 1.0 * extra_required - 0.15 * step_count`)*\n* **Step Count:** 4 steps\n* **Matched Pantry Ingredients:** `onions`, `tomatoes`\n* **Extra Required Ingredients (Missing from pantry):** `grreen chillie`\n* **Unused Pantry Ingredients:** `eggs` (excluded), `rice`\n\n---\n\n### 2. **Tstcgdgdgdgdgdgdgd** (Recipe ID: `fn_0ba6bc0a49c4f0aa`)\n* **Score:** 2.4\n* **Step Count:** 4 steps\n* **Matched Pantry Ingredients:** `onions`, `tomatoes`\n* **Extra Required Ingredients (Missing from pantry):** `grreen chillie`\n* **Unused Pantry Ingredients:** `eggs` (excluded), `rice`\n\n---\n\n### 3. **QA** (Recipe ID: `fn_20785db8d9cf36ce`)\n* **Score:** 1.85\n* **Step Count:** 1 step\n* **Matched Pantry Ingredients:** `rice`\n* **Extra Required Ingredients (Missing from pantry):** None\n* **Unused Pantry Ingredients:** `eggs` (excluded), `onions`, `tomatoes`\n\n---\n\n### 4. **Grilled Onions** (Recipe ID: `fn_61c77fd69c2f7cfa`)\n* **Score:** 1.55\n* **Step Count:** 3 steps\n* **Matched Pantry Ingredients:** `onions`\n* **Extra Required Ingredients (Missing from pantry):** None\n* **Unused Pantry Ingredients:** `eggs` (excluded), `rice`, `tomatoes`\n\n---\n\n### 5. **QATest2** (Recipe ID: `fn_14b1bfd546e89e0b`)\n* **Score:** 0.85\n* **Step Count:** 1 step\n* **Matched Pantry Ingredients:** `rice`\n* **Extra Required Ingredients (Missing from pantry):** `milk`\n* **Unused Pantry Ingredients:** `eggs` (excluded), `onions`, `tomatoes`",
  "state_after": "Pantry ingredients: eggs, onions, tomatoes, rice; Excluded ingredients/groups: peanuts, peanut, eggs, egg; Max steps: 6; Active recipe: fn_0768e679c73db70e; Last shown recipes: #1=fn_0768e679c73db70e, #2=fn_0ba6bc0a49c4f0aa, #3=fn_20785db8d9cf36ce, #4=fn_61c77fd69c2f7cfa, #5=fn_14b1bfd546e89e0b",
  "last_shown_recipe_ids": [
    "fn_0768e679c73db70e",
    "fn_0ba6bc0a49c4f0aa",
    "fn_20785db8d9cf36ce",
    "fn_61c77fd69c2f7cfa",
    "fn_14b1bfd546e89e0b"
  ],
  "passed": true,
  "elapsed_seconds": 17.49
}
```

## 04_no_match_edge_case

```json
{
  "test": "04_no_match_edge_case",
  "impossible_constraint_result": {
    "eligible_count": 0,
    "has_violating_alternatives": true,
    "no_match_reason": "No recipes satisfy all hard constraints (exclude_ingredients and/or max_steps).",
    "constraints_applied": {
      "exclude_ingredients": [
        "dairy",
        "eggs"
      ],
      "expanded_exclusions": [
        "asiago",
        "brie",
        "burrata",
        "butter",
        "buttermilk",
        "camembert",
        "casein",
        "cheddar",
        "cheddar cheese",
        "cheese",
        "condensed milk",
        "cotija",
        "cottage cheese",
        "cream",
        "cream cheese",
        "creme fraiche",
        "egg",
        "egg white",
        "egg yolk",
        "emmental",
        "evaporated milk",
        "feta",
        "fontina",
        "gelato",
        "ghee",
        "goat cheese",
        "gorgonzola",
        "gouda",
        "gruyere",
        "half and half",
        "half-and-half",
        "halloumi",
        "havarti",
        "heavy cream",
        "ice cream",
        "kefir",
        "lactose",
        "manchego",
        "mascarpone",
        "milk",
        "monterey jack",
        "mozzarella",
        "nonfat milk",
        "paneer",
        "parmesan",
        "parmigiano",
        "parmigiano-reggiano",
        "pecorino",
        "pecorino romano",
        "provolone",
        "queso",
        "queso fresco",
        "ricotta",
        "ricotta cheese",
        "romano",
        "roquefort",
        "skim milk",
        "sour cream",
        "stilton",
        "stracciatella",
        "sweetened condensed milk",
        "swiss",
        "whey",
        "whipping cream",
        "whole milk",
        "yogurt"
      ],
      "max_steps": 1,
      "pantry_normalized": [
        "butter",
        "egg",
        "milk"
      ]
    },
    "sample_alternative": {
      "recipe_id": "fn_297947138c387e2e",
      "title": "French Toast Buns",
      "step_count": 5,
      "matched_ingredients": [
        "butter",
        "egg",
        "milk"
      ],
      "missing_from_pantry": [
        "potato buns"
      ],
      "score": 4.25,
      "violated_constraints": [
        "contains excluded ingredients: ['butter', 'egg', 'milk']",
        "step_count 5 exceeds max_steps 1"
      ]
    }
  },
  "moderate_constraint_result": {
    "eligible_count": 5
  },
  "passed": true,
  "note": "Hard constraints are enforced \u2014 no silent relaxation.",
  "elapsed_seconds": 4.28
}
```

## 05_substitution_evidence

```json
{
  "test": "05_substitution_evidence",
  "banana_bread_recipe": {
    "recipe_id": "fn_5fc4405fbbe5cb9f",
    "title": "Banana Bread Chocolate Chip"
  },
  "egg_substitution": {
    "evidence_strength": "indirect",
    "candidate_count": 15,
    "supporting_recipes": 10,
    "top_candidates": [
      {
        "substitute": "semisweet chocolate chip",
        "supporting_recipe_count": 8,
        "count_in_similar_with_target": 0,
        "evidence_strength": "indirect",
        "supporting_recipe_ids": [
          "fn_eb05fd8204d5a704",
          "ar_ecf06079f5bf0101",
          "ar_6c36848923c2a3eb",
          "ar_502434bfd0d31856",
          "fn_23b0b1d799c0790e"
        ],
        "supporting_recipes": [
          {
            "recipe_id": "fn_eb05fd8204d5a704",
            "title": "Oatmeal Chocolate-Chip Peanut-Butter Banana Breakfast Cookies"
          },
          {
            "recipe_id": "ar_ecf06079f5bf0101",
            "title": "Chocolate Banana Oatmeal Porridge"
          },
          {
            "recipe_id": "ar_6c36848923c2a3eb",
            "title": "Flourless Double Chocolate Chip Zucchini Muffins"
          },
          {
            "recipe_id": "ar_502434bfd0d31856",
            "title": "Banana Boats"
          },
          {
            "recipe_id": "fn_23b0b1d799c0790e",
            "title": "Stuffed Chocolate and Peanut Butter Baked Bananas"
          }
        ]
      },
      {
        "substitute": "peanut butter",
        "supporting_recipe_count": 5,
        "count_in_similar_with_target": 0,
        "evidence_strength": "indirect",
        "supporting_recipe_ids": [
          "fn_eb05fd8204d5a704",
          "fn_23b0b1d799c0790e",
          "fn_3a90a1f5dfc0846f",
          "ar_97d0e433692898a8",
          "ar_ec4c23b0929a8e3a"
        ],
        "supporting_recipes": [
          {
            "recipe_id": "fn_eb05fd8204d5a704",
            "title": "Oatmeal Chocolate-Chip Peanut-Butter Banana Breakfast Cookies"
          },
          {
            "recipe_id": "fn_23b0b1d799c0790e",
            "title": "Stuffed Chocolate and Peanut Butter Baked Bananas"
          },
          {
            "recipe_id": "fn_3a90a1f5dfc0846f",
            "title": "Peanut Butter \"Corn\" Dog"
          },
          {
            "recipe_id": "ar_97d0e433692898a8",
            "title": "Craving Cookies"
          },
          {
            "recipe_id": "ar_ec4c23b0929a8e3a",
            "title": "Quinoa Cookies"
          }
        ]
      },
      {
        "substitute": "rolled oats",
        "supporting_recipe_count": 4,
        "count_in_similar_with_target": 0,
        "evidence_strength": "indirect",
        "supporting_recipe_ids": [
          "fn_eb05fd8204d5a704",
          "ar_ecf06079f5bf0101",
          "ar_a65666b50db4c46e",
          "ar_ec4c23b0929a8e3a"
        ],
        "supporting_recipes": [
          {
            "recipe_id": "fn_eb05fd8204d5a704",
            "title": "Oatmeal Chocolate-Chip Peanut-Butter Banana Breakfast Cookies"
          },
          {
            "recipe_id": "ar_ecf06079f5bf0101",
            "title": "Chocolate Banana Oatmeal Porridge"
          },
          {
            "recipe_id": "ar_a65666b50db4c46e",
            "title": "Delicious Banana Vegan Muffins (healthy and sugar free!)"
          },
          {
            "recipe_id": "ar_ec4c23b0929a8e3a",
            "title": "Quinoa Cookies"
          }
        ]
      }
    ]
  },
  "pasta_cream_substitution": {
    "evidence_strength": "indirect",
    "candidate_count": 15
  },
  "passed": true,
  "elapsed_seconds": 11.11
}
```

## 06_llm_comparison

```json
{
  "test": "06_llm_comparison",
  "grounded_garlic_count": {
    "numerator": 26764,
    "denominator": 124483,
    "percentage": 21.5,
    "source": "SQLite COUNT(*) over full dataset"
  },
  "naive_llm_answer": "Based on",
  "comparison_note": "The naive LLM cannot know the exact count without querying the database. It may hallucinate a plausible-sounding number. Our grounded system uses SQL COUNT(*) over the full dataset for an exact, reproducible answer.",
  "weak_evidence_case": {
    "recipe": "Saffron Rouille",
    "evidence_strength": "strong",
    "candidate_count": 15,
    "note": "If evidence is weak, system correctly flags uncertainty rather than hallucinating."
  },
  "passed": true,
  "elapsed_seconds": 2.38
}
```

## LLM Comparison Analysis

### Naive One-Shot LLM Answer

> Based on

### Grounded System Answer

- **Exact count**: 26764
- **Total recipes**: 124483
- **Percentage**: 21.5%
- **Source**: SQLite COUNT(*) over full dataset

**Key Difference**: The naive LLM cannot know the exact count without querying the database. It may hallucinate a plausible-sounding number. Our grounded system uses SQL COUNT(*) over the full dataset for an exact, reproducible answer.
