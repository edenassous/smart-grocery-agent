# 🛒 Smart Grocery Basket Agent

An AI agent that finds the cheapest grocery basket in Israel by comparing real-time prices across major supermarket chains and optimally splitting orders to minimize total cost (including delivery fees and minimum-order constraints).

> Built with Claude API + real price transparency data from Israeli supermarket chains (rami-levy, Shufersal, Victory).

---

## ✨ What it does

1. User types a shopping list in free Hebrew text
2. The agent identifies products and searches a database of ~400,000 prices from 3 chains
3. An ILP optimizer computes the cheapest split between chains, accounting for delivery fees and minimum order thresholds
4. Results are presented as separate baskets with savings comparison

**Example:**

Input:
> "Weekly basket for two: milk 3%, eggs, cottage cheese, butter, yogurt, pasta, tomato sauce, rice, olive oil, Coca-Cola, Bamba, Bissli, ice cream, toilet paper, laundry detergent"

Output:
> Optimal split between 2 chains, ₪355 total (including ₪50 delivery)

---

## 🏗️ Architecture

                ┌─────────────────────────────┐
                │  Next.js Frontend (:3000)   │
                │  React + Tailwind + SSE     │
                └──────────────┬──────────────┘
                               │ POST /api/search
                ┌──────────────▼──────────────┐
                │  FastAPI Server (:8000)     │
                │  SSE streaming endpoint     │
                └──────────────┬──────────────┘
                               │
                ┌──────────────▼──────────────┐
                │   Agent Layer               │
                │   Claude Opus 4 + 4 tools   │
                │                             │
                │   • parse_shopping_list     │
                │   • search_product          │
                │   • get_delivery_info       │
                │   • optimize_basket (ILP)   │
                └──────────────┬──────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │   Database   │  │    Search    │  │  Optimizer   │
     │   SQLite     │  │   rapidfuzz  │  │   PuLP/CBC   │
     │   400K rows  │  │   + custom   │  │   MILP       │
     │              │  │   scoring    │  │   solver     │
     └──────┬───────┘  └──────────────┘  └──────────────┘
            │
            │ Daily cron refresh
            │
     ┌──────▼────────────────────┐
     │  Pipeline                 │
     │  il-supermarket-scraper   │
     │  → 3 chains, 60+ XML/day  │
     │  → Custom XML parser      │
     │  → SQLite                 │
     └───────────────────────────┘

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend)
- Anthropic API key

### Backend setup

```bash
# Clone and install
git clone <repo-url>
cd veggie-agent
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY=sk-ant-...

# Initial data download (5-15 min)
python pipeline.py all

# Run via CLI
python main_real.py "I need milk, bread, eggs"

# Or run the API server
uvicorn api:app --reload --port 8000
```

### Frontend setup

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
# Open http://localhost:3000
```

### Daily refresh (optional)

```bash
crontab -e
# Add: 0 9 * * * cd /path/to/veggie-agent && python daily_refresh.py >> logs/refresh.log 2>&1
```

---

## 📂 Project structure

```text
smart-grocery-agent/
├── agent.py            Agent loop with streaming events
├── api.py              FastAPI server + SSE endpoint
├── main_real.py        CLI entry point
├── tools_real.py       Tools the agent can call
├── search_engine.py    Smart fuzzy search with custom scoring
├── optimizer.py        ILP solver (PuLP) for basket splitting
├── parser.py           XML → SQLite parser (handles 2 schemas)
├── pipeline.py         End-to-end data pipeline
├── daily_refresh.py    Cron-friendly daily update
├── frontend/
│   └── app/
│       ├── page.tsx    Main UI with SSE consumer
│       └── layout.tsx
└── README.md
```

---

## 🧩 Key technical decisions

### Why ILP instead of a greedy approach?

A greedy "cheapest store per item" misses two real-world constraints:
1. **Delivery fees** — splitting items across stores adds delivery cost per store
2. **Minimum order thresholds** — each store requires e.g. ₪150 minimum

The ILP formulation handles both as constraints, finding the global optimum. The objective function minimizes total cost = sum(items) + sum(delivery_fees * is_store_active) + skip_penalty * unfulfilled_items.

### Why barcode-based product matching?

Israeli supermarkets follow EAN-13 barcodes. The same Coca-Cola has the same `ItemCode` at Rami Levy, Shufersal, and Victory. This eliminates the painful name-matching problem of "חלב תנובה 3% 1 ליטר" vs "תנובה חלב טרי 3 אחוז" — match on barcode, not text.

### Why SSE instead of WebSocket?

The agent's progress is one-way (server → client). SSE is simpler, works over plain HTTP, auto-reconnects, and scales behind a load balancer without sticky sessions.

### Why soft constraints in the optimizer?

If an item is only available at Store A but the basket can't reach Store A's minimum order, the original solver returned `infeasible`. We added a high-penalty `skip` variable per item — the solver chooses to drop items only when it has no other choice, marking them as `unfulfilled` for the user. This converts a hard "no answer" into a partial answer with clear messaging.

### Why custom scoring on top of fuzzy search?

Pure `token_set_ratio` returns 100% for both "אבקת מרק" (soup powder) and "אבקת כביסה" (laundry powder) when the user searches for "soup powder". Solved with custom scoring layered on top:
- SQL prefilter (every search word must appear in the product name)
- Length bonus (shorter names → more generic products)
- Position bonus (search word appearing at the start)
- Variation penalty (terms like "snack", "puffed", "candy" reduce score unless explicitly searched)

---

## 📊 Stats

After a full daily refresh:
- **3 supermarket chains** (Rami Levy, Shufersal, Victory)
- **~400,000 price rows**
- **~50,000 unique products** (by EAN barcode)
- **~30 seconds** download time (with multiprocessing)
- **~10 seconds** parse time

---

## 🎓 What I learned building this

- **Real-world data is messy.** Three chains, three different XML schemas, all "compliant" with the same regulation. The parser handles `<Item>` vs `<Product>`, `bIsWeighted` vs `BisWeighted`, `<Root>` vs `<Prices>`.
- **Fuzzy search alone isn't enough for Hebrew.** Token-based matching gives identical scores to semantically very different products. Custom domain rules outperform generic algorithms.
- **Agents need clean tools.** The agent doesn't compute prices itself — it orchestrates. Each tool has one job. ILP runs deterministically; the LLM only presents results.
- **Soft constraints matter for UX.** Returning `infeasible` is a UX failure — much better to drop an item and explain than to give up entirely.
- **Streaming changes everything.** With 15 product searches happening serially, a 30-second wait feels broken. SSE streaming of progress events transforms the experience.

---

## 🛣️ Future work

- [ ] Embeddings-based product matching (e.g. E5-multilingual)
- [ ] Per-region delivery fees (currently uniform across regions)
- [ ] Add more chains (Yochananof, Osher Ad, Tiv Taam)
- [ ] PostgreSQL migration with `pg_trgm` for native Hebrew full-text search
- [ ] Promotion handling (`PROMO_FILE` from price transparency)
- [ ] User accounts + history of past baskets
- [ ] Mobile app (PWA)

---

## 📜 License

MIT

---

## 🙏 Credits

- [il-supermarket-scraper](https://github.com/OpenIsraeliSupermarkets/israeli-supermarket-scarpers) — handles all the chain-specific quirks of the Israeli price transparency portals
- [Anthropic Claude](https://www.anthropic.com/) — agent intelligence and tool orchestration

- [PuLP](https://coin-or.github.io/pulp/) — Linear programming frameworkfor the optimizer
