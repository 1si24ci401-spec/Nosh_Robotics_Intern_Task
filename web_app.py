#!/usr/bin/env python3
"""
web_app.py — Lightweight, zero-dependency Web UI for the Nosh Robotics Recipe Assistant.

Runs on Python standard library (http.server). No additional packages required.

Usage:
    python web_app.py [--port 8000]
    python app.py --web
"""

from __future__ import annotations

import argparse
import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from src import tools
from src.agent import RecipeAgent, create_agent

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent
GLOBAL_AGENT: RecipeAgent | None = None


def get_agent() -> RecipeAgent:
    global GLOBAL_AGENT
    if GLOBAL_AGENT is None:
        GLOBAL_AGENT = create_agent()
    return GLOBAL_AGENT


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nosh Robotics — Recipe Assistant</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    .prose p { margin-bottom: 0.5rem; }
    .prose ul { list-style-type: disc; margin-left: 1.25rem; margin-bottom: 0.5rem; }
    .prose ol { list-style-type: decimal; margin-left: 1.25rem; margin-bottom: 0.5rem; }
    .prose strong { color: #111827; }
    .prose code { background: #f3f4f6; padding: 0.1rem 0.3rem; border-radius: 0.25rem; font-size: 0.875rem; }
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col font-sans">
  <!-- Header -->
  <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
    <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <span class="text-2xl">🍳</span>
        <div>
          <h1 class="text-lg font-bold text-slate-900 leading-tight">Nosh Robotics Recipe Assistant</h1>
          <p class="text-xs text-slate-500">Deterministic Tool-Calling Architecture &middot; SQLite FTS5 (124k Recipes) &middot; Gemini</p>
        </div>
      </div>
      <div class="flex items-center space-x-2">
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
          <span class="w-1.5 h-1.5 mr-1.5 bg-emerald-500 rounded-full animate-pulse"></span> Grounded in SQLite
        </span>
      </div>
    </div>
  </header>

  <!-- Navigation Tabs -->
  <div class="bg-white border-b border-slate-200">
    <div class="max-w-6xl mx-auto px-4 flex space-x-1 sm:space-x-4 overflow-x-auto text-sm font-medium">
      <button onclick="switchTab('chat')" id="tab-chat" class="tab-btn px-4 py-3 border-b-2 border-emerald-600 text-emerald-600 font-semibold flex items-center gap-1.5">
        <span>💬</span> Conversational Chatbot
      </button>
      <button onclick="switchTab('task1')" id="tab-task1" class="tab-btn px-4 py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 flex items-center gap-1.5">
        <span>🔍</span> Task 1: Search & Stats
      </button>
      <button onclick="switchTab('task2')" id="tab-task2" class="tab-btn px-4 py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 flex items-center gap-1.5">
        <span>🛒</span> Task 2: Pantry Matcher
      </button>
      <button onclick="switchTab('task3')" id="tab-task3" class="tab-btn px-4 py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 flex items-center gap-1.5">
        <span>🔄</span> Task 3: Substitution
      </button>
      <button onclick="switchTab('eval')" id="tab-eval" class="tab-btn px-4 py-3 border-b-2 border-transparent text-slate-600 hover:text-slate-900 flex items-center gap-1.5">
        <span>📊</span> Evaluation Suite
      </button>
    </div>
  </div>

  <!-- Main Content Area -->
  <main class="max-w-6xl mx-auto px-4 py-6 flex-1 w-full">

    <!-- TAB 1: Chatbot -->
    <section id="panel-chat" class="tab-panel">
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <!-- Chat Area -->
        <div class="lg:col-span-3 flex flex-col h-[70vh] bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <!-- Messages -->
          <div id="chat-messages" class="flex-1 p-4 overflow-y-auto space-y-4">
            <div class="flex items-start gap-3">
              <div class="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-sm shrink-0">AI</div>
              <div class="bg-slate-100 rounded-2xl rounded-tl-none p-3.5 max-w-[85%] text-sm prose">
                <p>Hello! I am your grounded recipe assistant. I search, analyze, match, and adapt recipes directly from the <strong>124,483 recipes</strong> in the Eight Portions dataset.</p>
                <p class="text-xs text-slate-500">Try asking:</p>
                <div class="flex flex-wrap gap-1.5 mt-2 not-prose">
                  <button onclick="fillAndSend('Find me a penne pasta recipe')" class="chip">"Find penne pasta"</button>
                  <button onclick="fillAndSend('How many recipes contain both garlic and onion? What percentage?')" class="chip">"Garlic & Onion stats"</button>
                  <button onclick="fillAndSend('I have eggs, onions, tomatoes, and rice. Suggest 5 recipes, no peanuts, at most 6 steps.')" class="chip">"Pantry match"</button>
                  <button onclick="fillAndSend('Take this banana bread recipe and remove eggs.')" class="chip">"Banana bread without eggs"</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Input form -->
          <div class="p-3 bg-slate-50 border-t border-slate-200">
            <form onsubmit="handleSend(event)" class="flex gap-2">
              <input type="text" id="chat-input" placeholder="Ask a question (e.g. 'I cannot have dairy', 'Exclude eggs too')..." class="flex-1 px-4 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white">
              <button type="submit" id="send-btn" class="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm rounded-lg transition-colors">Send</button>
            </form>
          </div>
        </div>

        <!-- Sidebar / State Inspector -->
        <div class="space-y-4">
          <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
            <div class="flex items-center justify-between mb-3">
              <h3 class="font-semibold text-slate-900 text-sm">Session Memory State</h3>
              <button onclick="resetSession()" class="text-xs text-red-600 hover:text-red-700 font-medium">Reset (/reset)</button>
            </div>
            <div id="session-state-box" class="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-200 font-mono whitespace-pre-wrap leading-relaxed">No active filters.</div>
          </div>

          <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 text-xs space-y-2">
            <h4 class="font-semibold text-slate-900">Task 1 Multi-turn Walkthrough:</h4>
            <ol class="list-decimal list-inside space-y-1 text-slate-600">
              <li>Click <span class="font-mono text-emerald-700">"Find penne pasta"</span></li>
              <li>Then follow up: <span class="font-mono text-emerald-700">"I cannot have dairy"</span></li>
              <li>Agent automatically refines active search and excludes dairy products via SQL.</li>
            </ol>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 2: Task 1 - Search & Stats -->
    <section id="panel-task1" class="tab-panel hidden space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Search Box -->
        <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200 space-y-4">
          <h3 class="font-bold text-slate-900 text-base flex items-center gap-2">
            <span>🔍</span> SQLite FTS5 Recipe Search
          </h3>
          <div class="space-y-3">
            <div>
              <label class="block text-xs font-semibold text-slate-600 mb-1">Search Query (Title / Instructions / Keywords)</label>
              <input type="text" id="t1-query" value="penne pasta" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-semibold text-slate-600 mb-1">Exclude (e.g. dairy, peanuts)</label>
                <input type="text" id="t1-exclude" placeholder="dairy" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
              </div>
              <div>
                <label class="block text-xs font-semibold text-slate-600 mb-1">Max Instruction Steps</label>
                <input type="number" id="t1-max-steps" placeholder="Optional" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
              </div>
            </div>
            <button onclick="runTask1Search()" class="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm rounded-lg transition-colors">Search Dataset</button>
          </div>
        </div>

        <!-- Statistics Box -->
        <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200 space-y-4">
          <h3 class="font-bold text-slate-900 text-base flex items-center gap-2">
            <span>📊</span> Programmatic Dataset Statistics
          </h3>
          <div class="space-y-3">
            <div>
              <label class="block text-xs font-semibold text-slate-600 mb-1">Statistic Type</label>
              <select id="t1-stat-type" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
                <option value="count">Recipe Count & Percentage</option>
                <option value="fewest_steps">Rank by Fewest Steps</option>
                <option value="common_ingredients">Top Common Ingredients</option>
                <option value="avg_ingredients">Average & Median Ingredient Count</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-600 mb-1">Filter Ingredients (comma-separated)</label>
              <input type="text" id="t1-stat-include" value="garlic, onion" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
            </div>
            <button onclick="runTask1Stats()" class="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm rounded-lg transition-colors">Compute Exact Stats</button>
          </div>
        </div>
      </div>

      <!-- Result View -->
      <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
        <h4 class="font-semibold text-sm text-slate-900 mb-3">Deterministic Output</h4>
        <pre id="t1-output" class="bg-slate-900 text-emerald-400 p-4 rounded-lg text-xs font-mono overflow-x-auto max-h-96 whitespace-pre-wrap">Run a search or stat calculation above to see exact SQL outputs.</pre>
      </div>
    </section>

    <!-- TAB 3: Task 2 - Pantry Matcher -->
    <section id="panel-task2" class="tab-panel hidden space-y-6">
      <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200 space-y-4">
        <h3 class="font-bold text-slate-900 text-base flex items-center gap-2">
          <span>🛒</span> Ingredient-Based Pantry Matcher & Scoring
        </h3>
        <p class="text-xs text-slate-500">Uses the explainable formula: <code class="font-mono text-emerald-700">score = (2.0 &times; matched) &minus; (1.0 &times; extra_required) &minus; (0.15 &times; step_count)</code>. Hard constraints are never relaxed silently.</p>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="md:col-span-2">
            <label class="block text-xs font-semibold text-slate-600 mb-1">Available Pantry Ingredients (comma-separated)</label>
            <input type="text" id="t2-pantry" value="eggs, onions, tomatoes, rice" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-600 mb-1">Max Steps Constraint</label>
            <input type="number" id="t2-max-steps" value="6" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
          </div>
          <div class="md:col-span-2">
            <label class="block text-xs font-semibold text-slate-600 mb-1">Exclude Ingredients / Groups</label>
            <input type="text" id="t2-exclude" value="peanuts" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
          </div>
          <div class="flex items-end">
            <button onclick="runTask2Match()" class="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm rounded-lg transition-colors">Match Recipes</button>
          </div>
        </div>
      </div>

      <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
        <h4 class="font-semibold text-sm text-slate-900 mb-3">Ranked Pantry Matches</h4>
        <div id="t2-results" class="text-xs space-y-3 font-mono">
          <p class="text-slate-500 font-sans">Click "Match Recipes" above to view ranked results with score breakdown.</p>
        </div>
      </div>
    </section>

    <!-- TAB 4: Task 3 - Substitutions -->
    <section id="panel-task3" class="tab-panel hidden space-y-6">
      <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200 space-y-4">
        <h3 class="font-bold text-slate-900 text-base flex items-center gap-2">
          <span>🔄</span> Local Dataset Ingredient Substitution Mining
        </h3>
        <p class="text-xs text-slate-500">Mines up to 25 similar recipes in the dataset that omit the target ingredient to find data-backed replacement candidates and assess evidence strength.</p>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-xs font-semibold text-slate-600 mb-1">Recipe Name or ID</label>
            <input type="text" id="t3-recipe" value="banana bread" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-600 mb-1">Target Ingredient to Remove</label>
            <input type="text" id="t3-target" value="egg" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-600 mb-1">Dietary Restrictions (e.g. dairy)</label>
            <input type="text" id="t3-restrictions" value="dairy" class="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
          </div>
        </div>
        <button onclick="runTask3Sub()" class="w-full py-2 bg-purple-600 hover:bg-purple-700 text-white font-medium text-sm rounded-lg transition-colors">Mine Substitution Evidence</button>
      </div>

      <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
        <h4 class="font-semibold text-sm text-slate-900 mb-3">Substitution Analysis & Supporting Recipe Citations</h4>
        <pre id="t3-output" class="bg-slate-900 text-purple-300 p-4 rounded-lg text-xs font-mono overflow-x-auto max-h-96 whitespace-pre-wrap">Click "Mine Substitution Evidence" above to inspect supporting recipes.</pre>
      </div>
    </section>

    <!-- TAB 5: Evaluation Results -->
    <section id="panel-eval" class="tab-panel hidden space-y-4">
      <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="font-bold text-slate-900 text-base">Reproducible Evaluation Suite (EVAL_RESULTS.md)</h3>
            <p class="text-xs text-slate-500">Live scorecard and test outputs generated by <code>python eval.py</code></p>
          </div>
          <button onclick="loadEvalReport()" class="px-3 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-medium">Refresh</button>
        </div>
        <div id="eval-markdown" class="prose max-w-none text-xs text-slate-700">Loading evaluation report...</div>
      </div>
    </section>
  </main>

  <script>
    function switchTab(name) {
      document.querySelectorAll('.tab-panel').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.remove('border-emerald-600', 'text-emerald-600', 'font-semibold');
        el.classList.add('border-transparent', 'text-slate-600');
      });
      document.getElementById('panel-' + name).classList.remove('hidden');
      const activeBtn = document.getElementById('tab-' + name);
      activeBtn.classList.add('border-emerald-600', 'text-emerald-600', 'font-semibold');
      activeBtn.classList.remove('border-transparent', 'text-slate-600');

      if (name === 'eval') loadEvalReport();
      if (name === 'chat') updateStateBox();
    }

    async function handleSend(e) {
      if (e) e.preventDefault();
      const input = document.getElementById('chat-input');
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      appendMessage('user', text);

      const btn = document.getElementById('send-btn');
      btn.disabled = true;
      btn.innerText = 'Thinking...';

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({message: text})
        });
        const data = await res.json();
        appendMessage('assistant', data.response);
        updateStateBox(data.state);
      } catch (err) {
        appendMessage('assistant', 'Error: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerText = 'Send';
      }
    }

    function fillAndSend(text) {
      document.getElementById('chat-input').value = text;
      handleSend();
    }

    function appendMessage(role, text) {
      const container = document.getElementById('chat-messages');
      const div = document.createElement('div');
      div.className = 'flex items-start gap-3 ' + (role === 'user' ? 'justify-end' : '');

      if (role === 'user') {
        div.innerHTML = `<div class="bg-emerald-600 text-white rounded-2xl rounded-tr-none p-3.5 max-w-[85%] text-sm">${escapeHtml(text)}</div>`;
      } else {
        const parsed = marked.parse(text);
        div.innerHTML = `
          <div class="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-sm shrink-0">AI</div>
          <div class="bg-slate-100 rounded-2xl rounded-tl-none p-3.5 max-w-[85%] text-sm prose">${parsed}</div>
        `;
      }
      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
    }

    async function updateStateBox(stateStr) {
      const box = document.getElementById('session-state-box');
      if (stateStr) {
        box.innerText = stateStr;
        return;
      }
      try {
        const res = await fetch('/api/state');
        const data = await res.json();
        box.innerText = data.summary || 'No active filters.';
      } catch (e) {
        box.innerText = 'Error fetching state.';
      }
    }

    async function resetSession() {
      await fetch('/api/reset', {method: 'POST'});
      updateStateBox('Session cleared. Starting fresh.');
      appendMessage('assistant', '✓ Session state cleared. All active filters have been reset.');
    }

    async function runTask1Search() {
      const query = document.getElementById('t1-query').value;
      const exclude = document.getElementById('t1-exclude').value;
      const maxSteps = document.getElementById('t1-max-steps').value;
      const out = document.getElementById('t1-output');
      out.innerText = 'Searching SQLite...';

      const res = await fetch('/api/search', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          query,
          exclude_ingredients: exclude ? exclude.split(',').map(s=>s.trim()) : [],
          max_steps: maxSteps ? parseInt(maxSteps) : null
        })
      });
      const data = await res.json();
      out.innerText = JSON.stringify(data, null, 2);
    }

    async function runTask1Stats() {
      const stat_type = document.getElementById('t1-stat-type').value;
      const include = document.getElementById('t1-stat-include').value;
      const out = document.getElementById('t1-output');
      out.innerText = 'Computing exact counts & percentages over complete result set...';

      const res = await fetch('/api/stats', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          stat_type,
          include_ingredients: include ? include.split(',').map(s=>s.trim()) : []
        })
      });
      const data = await res.json();
      out.innerText = JSON.stringify(data, null, 2);
    }

    async function runTask2Match() {
      const pantry = document.getElementById('t2-pantry').value.split(',').map(s=>s.trim());
      const maxSteps = document.getElementById('t2-max-steps').value;
      const exclude = document.getElementById('t2-exclude').value;
      const out = document.getElementById('t2-results');
      out.innerHTML = '<p class="text-slate-500 font-sans">Matching against 124,483 recipes...</p>';

      const res = await fetch('/api/pantry', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          available_ingredients: pantry,
          max_steps: maxSteps ? parseInt(maxSteps) : null,
          exclude_ingredients: exclude ? exclude.split(',').map(s=>s.trim()) : []
        })
      });
      const data = await res.json();
      if (!data.eligible_recipes || data.eligible_recipes.length === 0) {
        out.innerHTML = `
          <div class="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg font-sans">
            <strong>No eligible recipes found!</strong> Hard constraints were not relaxed.
            <div class="mt-2 text-xs">Closest alternatives violating constraints:</div>
            <pre class="mt-1 text-xs text-red-900 bg-red-100 p-2 rounded overflow-x-auto">${JSON.stringify(data.closest_violating_alternatives, null, 2)}</pre>
          </div>`;
        return;
      }
      out.innerHTML = data.eligible_recipes.map((r, i) => `
        <div class="p-3.5 bg-slate-50 border border-slate-200 rounded-lg font-sans">
          <div class="flex items-center justify-between">
            <span class="font-bold text-slate-900">#${i+1} ${r.title}</span>
            <span class="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded font-bold text-xs">Score: ${r.score}</span>
          </div>
          <div class="text-xs text-slate-500 mt-0.5">ID: <code>${r.recipe_id}</code> &middot; Steps: ${r.step_count}</div>
          <div class="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div class="text-emerald-700"><strong>Matched (${r.matched_ingredients.length}):</strong> ${r.matched_ingredients.join(', ') || 'none'}</div>
            <div class="text-amber-700"><strong>Missing from Pantry (${r.missing_from_pantry.length}):</strong> ${r.missing_from_pantry.slice(0, 5).join(', ')}${r.missing_from_pantry.length > 5 ? '...' : ''}</div>
          </div>
          <div class="mt-1 text-[11px] text-slate-500 italic">${r.ranking_explanation}</div>
        </div>
      `).join('');
    }

    async function runTask3Sub() {
      const recipe = document.getElementById('t3-recipe').value;
      const target = document.getElementById('t3-target').value;
      const restrictions = document.getElementById('t3-restrictions').value;
      const out = document.getElementById('t3-output');
      out.innerText = 'Mining similar recipes in SQLite...';

      const res = await fetch('/api/substitution', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          recipe_id_or_title: recipe,
          target_ingredient: target,
          restrictions: restrictions ? restrictions.split(',').map(s=>s.trim()) : []
        })
      });
      const data = await res.json();
      out.innerText = JSON.stringify(data, null, 2);
    }

    async function loadEvalReport() {
      const el = document.getElementById('eval-markdown');
      el.innerText = 'Loading EVAL_RESULTS.md...';
      try {
        const res = await fetch('/api/eval');
        const text = await res.text();
        el.innerHTML = marked.parse(text);
      } catch (e) {
        el.innerText = 'Failed to load report.';
      }
    }

    function escapeHtml(text) {
      const map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
      return text.replace(/[&<>"']/g, m => map[m]);
    }
  </script>
</body>
</html>
"""


class RecipeRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/state":
            agent = get_agent()
            state_data = {
                "summary": agent.state.to_summary(),
                "include_ingredients": agent.state.include_ingredients,
                "exclude_ingredients": agent.state.exclude_ingredients,
                "max_steps": agent.state.max_steps,
                "active_recipe_id": agent.state.active_recipe_id,
                "last_shown_recipe_ids": agent.state.last_shown_recipe_ids,
            }
            self._send_json(state_data)
        elif parsed.path == "/api/eval":
            eval_path = PROJECT_ROOT / "EVAL_RESULTS.md"
            if eval_path.exists():
                content = eval_path.read_text(encoding="utf-8")
            else:
                content = "# Evaluation Results\nNo results found. Run `python eval.py` first."
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        if parsed.path == "/api/chat":
            msg = body.get("message", "").strip()
            agent = get_agent()
            response_text = agent.chat(msg) if msg else "Please enter a message."
            self._send_json({"response": response_text, "state": agent.state.to_summary()})

        elif parsed.path == "/api/reset":
            agent = get_agent()
            agent.reset()
            self._send_json({"status": "ok", "message": "Session reset."})

        elif parsed.path == "/api/search":
            result = tools.search_recipes(
                query=body.get("query", ""),
                include_ingredients=body.get("include_ingredients"),
                exclude_ingredients=body.get("exclude_ingredients"),
                max_steps=body.get("max_steps"),
                limit=body.get("limit", 10),
            )
            self._send_json(result)

        elif parsed.path == "/api/stats":
            result = tools.compute_dataset_stats(
                stat_type=body.get("stat_type", "count"),
                include_ingredients=body.get("include_ingredients"),
                exclude_ingredients=body.get("exclude_ingredients"),
                group_by=body.get("group_by"),
                top_n=body.get("top_n", 10),
            )
            self._send_json(result)

        elif parsed.path == "/api/pantry":
            result = tools.match_pantry_recipes(
                available_ingredients=body.get("available_ingredients", []),
                exclude_ingredients=body.get("exclude_ingredients"),
                max_steps=body.get("max_steps"),
                limit=body.get("limit", 5),
            )
            self._send_json(result)

        elif parsed.path == "/api/substitution":
            result = tools.find_substitution_evidence(
                recipe_id_or_title=body.get("recipe_id_or_title", ""),
                target_ingredient=body.get("target_ingredient", ""),
                restrictions=body.get("restrictions"),
            )
            self._send_json(result)

        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

    def _send_json(self, data: Any):
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any):
        # Concise logging
        logger.info("%s - %s", self.address_string(), format % args)


def run_web(port: int = 8000):
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, RecipeRequestHandler)
    print(f"\n🚀 Nosh Robotics Recipe Assistant Web UI running at: http://localhost:{port}")
    print("Press Ctrl+C to stop the server.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description="Web UI for Nosh Robotics Recipe Assistant")
    parser.add_argument("--port", type=int, default=8000, help="Port to run web server on (default: 8000)")
    args = parser.parse_args()
    run_web(port=args.port)


if __name__ == "__main__":
    main()
