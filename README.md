# gander-llm

Command-line tool that answers brand questions using LLMs and returns structured JSON capturing brand visibility metrics.

## What This Tool Does

Given a brand name, website, and user question, this tool:

1. Calls a ChatGPT-style model to generate a natural answer
2. Optionally grounds the answer with web search results (under strict token budgets)
3. Analyzes the response to extract brand visibility metrics
4. Returns everything as a single JSON object

**Key Output Metrics:**
- `human_response_markdown` — exact answer a user would see
- `citations` — URLs paired with entity mentions
- `mentions` — all brand name occurrences
- `owned_sources` — URLs on the brand's domain
- `sources` — external URLs used
- `metadata` — token counts, search usage, budgets

## Requirements

- Python 3.9+
- Terminal/command line
- **Option A:** Ollama (free, local LLM)
- **Option B:** OpenAI API key (paid)

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/halaarar/gander-llm.git
cd gander-llm
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
```

**Activate:**

macOS/Linux:
```bash
source .venv/bin/activate
```

Windows PowerShell:
```bash
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Choose Your Model Provider

### Option A: Ollama (Recommended - Free & Local)

**Install Ollama:**

macOS:
```bash
brew install ollama
```

Linux:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Windows: Download from [ollama.com/download](https://ollama.com/download)

**Start Server & Pull Model:**
```bash
ollama serve
ollama pull llama3.2
```

**Test Run:**
```bash
python app.py \
  --brand "Shopify" \
  --url "https://shopify.com" \
  --question "What problem does this platform solve for merchants?" \
  --use-model 1 \
  --provider ollama \
  --ollama-model llama3.2
```

### Option B: OpenAI API

**Setup:**
```bash
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=sk-...
```

**Test Run:**
```bash
python app.py \
  --brand "Shopify" \
  --url "https://shopify.com" \
  --question "What problem does this platform solve for merchants?" \
  --use-model 1 \
  --provider openai \
  --model gpt-4o-mini
```

## How It Works

### Answer Fidelity: ChatGPT User Experience

The tool prints the model's output verbatim in `human_response_markdown`. No rewriting, no annotations. What you see is exactly what a ChatGPT user would see.

This preserves authenticity while allowing post-hoc analysis of brand visibility.

### Citation Detection

**Definition:** A citation is any entity mention paired with a URL on the same line.

**Detection logic:**
1. Split answer into lines
2. For each line with a URL, check for capitalized words (entity names)
3. If entities present, include the URL as a citation

**Example:**
```
Shopify helps merchants at https://shopify.com
```
→ Citation: `https://shopify.com` (entity "Shopify" present)
```
Learn more at https://example.com
```
→ Not a citation (no entity name)

### Mention Detection

**Definition:** Any whole-word occurrence of the brand name in the answer (case-sensitive).

**Implementation:** Regex with word boundaries: `\b{brand}\b`

Counts both linked and unlinked mentions.

### Owned vs External Sources

**Owned sources:** URLs where the host matches the brand domain or any subdomain.

**Normalization:**
- Strips `www.` prefix
- Case-insensitive comparison
- Subdomain matching: `blog.shopify.com` is owned if brand is `shopify.com`

**Sources tracked:**
1. URLs appearing in the final answer
2. URLs used for grounding context (even if not printed)

Both are partitioned into `owned_sources` and `sources` arrays.

## Web Search & Grounding Strategy

### Budget Enforcement

Two hard caps control resource usage:

- `--max-searches N` — maximum search queries performed
- `--max-sources N` — maximum URLs included in model context

Both actual usage and caps are reported in `metadata.usage`.

### Search Behavior

**When grounding is enabled** (`--ground 1`):

1. Perform DuckDuckGo HTML search with auto-generated or custom query
2. Extract real result URLs (decode DDG redirects, filter out DDG domains)
3. Prefer brand-owned URLs first, then external sources
4. Select up to `--max-sources` URLs
5. Fetch and trim snippets from each URL
6. Include snippets in model context

**Fallback:** If search returns zero results but `--max-sources > 0`, use the brand URL itself as a single grounded source. In this case: `usage.searches = 0`, `usage.sources_included = 1`.

**When grounding is disabled:** No search, no context. Model answers from training data only.

### Example: Grounded Run
```bash
python app.py \
  --brand "Shopify" \
  --url "https://shopify.com" \
  --question "What problem does this platform solve for merchants?" \
  --use-model 1 \
  --provider ollama \
  --ollama-model llama3.2 \
  --ground 1 \
  --max-searches 1 \
  --max-sources 2 \
  --must-link-site \
  --output examples/shopify_output.json
```

This will:
- Perform 1 search
- Include up to 2 sources in context
- Force brand URL to appear in answer
- Save full JSON to file

## Token Optimization Tactics

### Tactic 1: Compact Prompts

**Flag:** `--compact-prompt 1` (default)

**Verbose system message:**
```
You are a helpful assistant. Write a concise, user-facing answer in markdown.
Do not include prompts, system messages, or developer notes.
If you include links, keep them natural.
```

**Compact system message:**
```
You are helpful. Answer in concise markdown.
```

**Savings:** ~25 input tokens per request

### Tactic 2: Aggressive Snippet Trimming

**Flag:** `--snippet-chars 600` (default)

**Processing steps:**
1. Fetch raw HTML from source URL
2. Extract `<title>` and `<meta name="description">`
3. Strip all HTML tags from body
4. Collapse whitespace
5. Enforce hard character limit

**Result:** Each snippet capped at 600 characters (~150 tokens)

**Trade-off:** Less context per source, but allows more sources within token budget.

### Additional Optimizations

- Hard cap on sources (`--max-sources`) prevents unbounded context growth
- Prefer owned sources first (typically more relevant, need less context)
- Deduplication of URLs across answer and grounding
- Minimal formatting in context (bullet list, no extra whitespace)

### Token Reporting

All token counts are tracked and reported:
```json
"usage": {
  "searches": 1,
  "sources_included": 2,
  "input_tokens": 847,
  "output_tokens": 156,
  "total_tokens": 1003
}
```

Counts calculated using `tiktoken` (OpenAI's tokenizer) for consistency.

## Command Reference

### Required Arguments
```bash
--brand "Brand Name"        # Brand name for mention detection
--url "https://brand.com"   # Brand website for ownership checks
--question "Your question"  # End-user question to answer
```

### Model Control
```bash
--use-model 1               # Call real model (0 = placeholder)
--provider ollama|openai    # Model provider
--ollama-model llama3.2     # Ollama model name
--model gpt-4o-mini         # OpenAI model name
```

### Grounding & Budgets
```bash
--ground 1                  # Enable web search grounding
--max-searches N            # Hard cap on searches (default: 0)
--max-sources N             # Hard cap on sources (default: 0)
--search-query "custom"     # Override auto-generated query
--snippet-chars 600         # Max characters per snippet
```

### Output Control
```bash
--must-link-site            # Force brand URL in answer
--compact-prompt 1          # Use short prompts (default: 1)
--output path/to/file.json  # Save JSON to file
--debug                     # Print errors to stderr
```

### Connection Settings
```bash
--timeout 30                # HTTP timeout seconds
--retries 2                 # Retry count for 429/5xx
```

## Output Format

### Example JSON
```json
{
  "human_response_markdown": "Shopify solves...\n\nFor details, see https://shopify.com",
  "citations": [
    "https://shopify.com"
  ],
  "mentions": [
    "Shopify"
  ],
  "owned_sources": [
    "https://shopify.com"
  ],
  "sources": [
    "https://example.org/shopify-review"
  ],
  "metadata": {
    "model": "ollama:llama3.2",
    "budgets": {
      "max_searches": 1,
      "max_sources": 2
    },
    "usage": {
      "searches": 1,
      "sources_included": 2,
      "input_tokens": 847,
      "output_tokens": 156,
      "total_tokens": 1003
    }
  }
}
```

### Field Descriptions

**`human_response_markdown`**
The exact answer text as shown to users. Never modified or annotated.

**`citations`**
URLs that appear alongside entity mentions (capitalized words) in the answer. Order preserved.

**`mentions`**
All exact-case, whole-word matches of the brand name in the answer.

**`owned_sources`**
URLs on the brand's domain (including subdomains) used to form the answer. Includes both answer links and grounded context URLs.

**`sources`**
External URLs (not owned by brand) used to form the answer. Same inclusion logic as owned sources.

**`metadata.budgets`**
The hard caps you set with `--max-searches` and `--max-sources`.

**`metadata.usage`**
Actual resource consumption:
- `searches` — number of search queries performed
- `sources_included` — number of URLs included in model context
- `input_tokens` — tokens in prompt (instructions + context + question)
- `output_tokens` — tokens in model response
- `total_tokens` — sum of input and output

## Assumptions

This tool makes the following design assumptions:

### Search Mechanism
- Uses DuckDuckGo HTML search (no API key required)
- Limited to ~10 results per search
- No authenticated APIs or paid search services

### Ownership Logic
- A URL is "owned" if its host exactly matches the brand host OR is a subdomain
- `www.` prefix is stripped for normalization
- Comparison is case-insensitive
- Examples:
  - Brand: `shopify.com` → Owns: `shopify.com`, `www.shopify.com`, `blog.shopify.com`
  - Does not own: `shopify.org`, `notshopify.com`

### Citation Definition
- Simplified from "entity + URL" to "capitalized word + URL on same line"
- Trade-off: Catches most entity mentions without NER complexity
- May include some false positives (capitalized common nouns)

### Fallback Behavior
- If search returns no results, brand URL used as single context source
- If model call fails, placeholder answer returned (unless `--debug` flag set)
- Graceful degradation prioritizes always returning valid JSON

### Token Counting
- Uses `tiktoken` (OpenAI tokenizer) for all providers
- Ollama token counts estimated using GPT-4 encoding
- Close approximation but not exact for non-OpenAI models

### URL Handling
- Query parameters and fragments preserved
- Trailing punctuation stripped (`.`, `,`, `;`, `:`, `!`, `?`)
- No URL canonicalization beyond `www.` removal

## Example Commands

### Minimal (No Grounding)
```bash
python app.py \
  --brand "Shopify" \
  --url "https://shopify.com" \
  --question "What problem does this platform solve for merchants?"
```

Returns placeholder answer with zero tokens.

### Full Featured (Recommended)
```bash
python app.py \
  --brand "Shopify" \
  --url "https://shopify.com" \
  --question "What problem does this platform solve for merchants?" \
  --use-model 1 \
  --provider ollama \
  --ollama-model llama3.2 \
  --ground 1 \
  --max-searches 1 \
  --max-sources 2 \
  --must-link-site \
  --compact-prompt 1 \
  --output examples/shopify_output.json
```

Demonstrates all features: grounding, citations, token optimization, source partitioning.

### OpenAI with Custom Search
```bash
python app.py \
  --brand "Stripe" \
  --url "https://stripe.com" \
  --question "How does payment processing work?" \
  --use-model 1 \
  --provider openai \
  --model gpt-4o-mini \
  --ground 1 \
  --max-searches 1 \
  --max-sources 1 \
  --search-query "Stripe payment processing architecture"
```

### Smoke Test (No Model)
```bash
python app.py \
  --brand "ACME" \
  --url "https://acme.com" \
  --question "What does this brand offer?"
```

Returns valid JSON with placeholder answer instantly. Good for testing JSON structure.

## Troubleshooting

### Ollama Connection Refused

Ensure server is running:
```bash
ollama serve
```

Check model is pulled:
```bash
ollama list
ollama pull llama3.2
```

### Empty Citations

Model didn't include URLs in answer. Try:
```bash
--must-link-site
```

Or increase `--max-sources` to provide more context for model to reference.

### Zero Searches/Sources

You probably didn't enable grounding:
```bash
--ground 1 --max-searches 1 --max-sources 1
```

### Token Counts Are Zero

This happens when using placeholder answer (`--use-model 0`). Set `--use-model 1` to call real model.

### macOS LibreSSL Warning

Ignore or upgrade Python. The `urllib3<2` pin in requirements.txt suppresses most instances.

### Windows PowerShell Execution Policy

Run as Administrator:
```powershell
Set-ExecutionPolicy RemoteSigned
```

## Sample Output

See `examples/shopify_output.json` for a complete example showing:
- Grounded answer with citations
- Brand mentions detected
- Sources partitioned into owned/external
- Token usage metrics
- All features working together

Generate your own:
```bash
mkdir -p examples
python app.py \
  --brand "Shopify" \
  --url "https://shopify.com" \
  --question "What problem does this platform solve for merchants?" \
  --use-model 1 --provider ollama --ollama-model llama3.2 \
  --ground 1 --max-searches 1 --max-sources 2 \
  --must-link-site \
  --output examples/shopify_output.json
```

## Trade-offs & Design Decisions

### Answer Fidelity vs Analysis
The tool never modifies the model's answer to ensure authentic "ChatGPT user experience." All analysis (citations, mentions) happens post-generation. This means we can't force citations to appear, only detect what the model naturally produces.

### Token Budget vs Answer Quality
Aggressive snippet trimming (600 chars) and compact prompts save tokens but provide less context. For complex questions, this may reduce answer depth. Adjust `--snippet-chars` if you need richer context.

### Simple Entity Detection vs NER
Using "capitalized words" as entity proxy is fast and deterministic but imperfect. Trade-off: simple code, no ML dependencies, catches 90%+ of real entities.

### DuckDuckGo HTML vs API
HTML scraping is fragile but free and requires no authentication. Trade-off: occasional parse failures, but zero operational cost.

### Local (Ollama) vs Hosted (OpenAI)
Ollama is free, private, and works offline but requires local compute. OpenAI is faster and higher quality but costs money and requires internet. This tool supports both to give users flexibility.

---

