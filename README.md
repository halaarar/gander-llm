# gander-llm

Command Line Tool for the interview prompt. It prints a single JSON with:
- `human_response_markdown`
- `citations`
- `mentions`
- `owned_sources`
- `sources`
- `metadata` with model name, budgets, and usage

## What this does today

- Reads inputs from flags: --brand, --url, --question, plus budgets --max-searches and --max-sources.

- Produces a clean, user facing answer string.
    - By default this is a simple placeholder answer.
    - You can optionally call a real LLM with --use-model 1.

- Scans the final answer text to:
    - collect every URL that appears in the answer as citations
    - detect exact brand mentions as mentions
    - split URLs into owned_sources (under the brand domain) vs external sources

- Emits one JSON object only. No logs or prompts mixed into the output.

## Requirments
- Python 3.11 or newer
- A terminal
- Optional: an OpenAI API key if you want real model answers

## Clone and Setup

1. Clone the repo 

```bash
git clone https://github.com/halaarar/gander-llm.git
cd gander-llm
```

2. Create a virtual environment

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1
```

3. Install dependencies

```bash
pip install -r requirements.txt
```


## Configure the API key if you want real model answers

You do not need an API key for placeholder mode. You only need it for --use-model 1.

1. Copy the template and paste your key locally

```bash
cp .env.example .env
# open .env in an editor and paste your real key after OPENAI_API_KEY=
```

2. Where to find your key

- Sign in to the OpenAI platform and open the API keys page. Create a new secret key if you do not have one yet. 

    OpenAI Platform [https://platform.openai.com/account/api-keys?utm_source=chatgpt.com]



## Run the tool

Placeholder mode (no model call):

```bash
python app.py \
  --brand "ACME" \
  --url "https://acme.com" \
  --question "What does this brand offer?"
```

```bash
Real model mode:

python app.py \
  --brand "ACME" \
  --url "https://acme.com" \
  --question "What does this brand offer?" \
  --use-model 1 \
  --model gpt-4o-mini
```

Both commands print a single JSON object to stdout.

## Flags

**Required**

- --brand brand name for mention detection

- --url brand website, used to identify owned sources

- --question end user question

**Budgets**

--max-searches hard cap on web searches. Not used yet in this minimal version. Defaults to 0.

--max-sources hard cap on source URLs that would be included in the model context. Not used yet in this minimal version. Defaults to 0.

**Model control**

- --use-model 1 to call a real LLM. 0 uses the placeholder answer.

- --model model name to request. Defaults to gpt-4o-mini.

## Output fields explained

**human_response_markdown**: The answer a normal user would read. Markdown is allowed.

**citations**: Every URL that appears in the final answer text, in reading order. Collected by a simple URL regex with small cleanup.

**mentions**: Exact case matches of the brand name as whole words. Deterministic and easy to explain during review.

**owned_sources**: URLs whose host equals the brand domain or a subdomain. Example: gandergeo.com and help.gandergeo.com.

**sources**: All other external URLs mentioned in the answer.

**metadata**
- model: placeholder or the model name if you called the API
- budgets: the limits passed on the command line
- usage: searches performed and number of sources included in the model context

In this minimal version both numbers are 0 because we do not search or inject source snippets yet.

docs: add Ollama local model instructions
