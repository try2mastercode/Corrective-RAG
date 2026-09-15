# Corrective RAG — Self-Evaluating Local Llama

A RAG pipeline that double-checks itself: grades its own retrieval, rewrites the query and
retries if the results are weak, falls back to web search if it has to, and verifies every
claim in the final answer against the evidence before showing it to you. Runs fully local on
Ollama by default, with Groq/OpenRouter as opt-in cloud fallbacks.

Benchmarked against a plain baseline RAG pipeline with RAGAS — see [Evaluation](#evaluation).

## Stack

- FastAPI backend (Python 3.11)
- Ollama for the LLM (`llama3.2:3b`), Groq/OpenRouter optional
- `sentence-transformers` for embeddings, Chroma for the vector store — both local always
- DuckDuckGo for web fallback, no API key
- Plain HTML/CSS/JS frontend, no build step
- RAGAS for evaluation

No Docker.

## Setup

```bash
git clone https://github.com/tharunsridhar/Corrective-RAG.git
cd Corrective-RAG

py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

copy .env.example .env
```

Using the local model? Pull it first:

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5:7b-instruct   # only if you'll run the evaluation
```

## Running it

```bash
python -m scripts.run_dev
```

Backend on `:8000`, frontend on `:5500`. Ctrl+C stops both. Open `http://localhost:5500`.

Separately, if you want split logs:

```bash
uvicorn app.main:app --reload --reload-dir app
python -m http.server 5500 --directory frontend
```

Or skip the UI entirely:

```bash
python -m scripts.ingest ./data/raw/some_document.pdf
python -m scripts.ask "What does the document say about X?"
```

## Cloud LLM (optional)

Local by default — nothing leaves your machine unless you turn this on. Flip it and your
questions and documents go to whichever provider you pick. Embeddings and the vector store
stay local regardless.

I tried both. Groq's the better pick — OpenRouter's free tier shares a pool and rate-limits
fast, Groq gives you your own quota and answers in a few seconds instead of a minute-plus.

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=allam-2-7b
```

Key's free at [console.groq.com/keys](https://console.groq.com/keys), no card. Stay away from
"reasoning" models (`openai/gpt-oss-20b`, `groq/compound-mini`) — they spend the token budget
on hidden thinking output and hit rate limits fast. `allam-2-7b` is plain and reliable.

OpenRouter, if you'd rather:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=liquid/lfm-2.5-2.6b:free
```

Restart the backend either way.

## How it works

```
question
   → retrieve top-k chunks (Chroma)
   → grade relevance
       weak?  → rewrite query → retrieve again
       still weak? → web search fallback
   → build evidence list (deduped, cited E1/E2/...)
   → generate answer
   → extract claims → verify against evidence
       unsupported? → correct and re-verify
   → answer + sources + status
```

Set `debug: true` on `/ask` (or tick "Debug mode" in the UI) to see every step.

### `/ask/agentic` — the model decides, not the pipeline

Everything above is a fixed pipeline: a Python `if` statement decides when to rewrite the query
or fall back to web search, based on a retrieval-quality score. `/ask/agentic` is a separate
endpoint (same request/response shape as `/ask`) where the model itself is handed a `web_search`
tool definition and decides, per question, whether the retrieved evidence is enough or it needs
to search — real tool-calling, not branching logic that calls the tool on the model's behalf.

```
question
   → retrieve top-k chunks (no grading pass)
   → LLM sees the evidence + a web_search tool definition
       model decides: answer now, or call web_search(query)?
       (repeats, bounded by max_tool_rounds, until the model stops calling the tool)
   → answer + sources (local + any web results the model chose to fetch)
```

Requires an LLM provider whose client implements `generate_with_tools` — OpenRouter and Groq do
(standard OpenAI-style function calling). Ollama's `/api/chat` supports it too, but tool-calling
reliability on this project's default local model (`llama3.2:3b`) is noticeably weaker than on a
larger hosted model — a bigger local model (`qwen2.5:7b-instruct`, already used for RAGAS
judging) will call the tool more reliably if you want to stay fully local. This endpoint skips
claim verification (see `grounding_status: "NOT_VERIFIED"` in its response) since verifying a
decision already produced by tool selection is redundant for a comparison endpoint like this one.

## Evaluation

```bash
python -m scripts.evaluate --limit 5      # quick
python -m scripts.evaluate                # full set, ~3hrs on CPU
```

Runs baseline and CRAG over the same questions, scores both with RAGAS, writes a report. RAGAS
needs a bigger model to judge with (`qwen2.5:7b-instruct`) — the small pipeline model gives
unreliable scores judging its own work, and the bigger one is slow on CPU, hence the runtime.
A sample report's checked in at [`data/evaluation/report.md`](data/evaluation/report.md).

## Known limitations

- Eval set is 24 questions; growing it just means more runtime
- RAGAS pinned to `0.1.21` — newer versions break on a missing import
- Local and web evidence aren't scored on the same scale
- Upload size capped at 20MB after the fact, not streamed — fine for local use, not for public-facing
- Run traces live in memory, last 500, gone on restart
- Small corpora can make retrieval look weak even when it found the right chunk — tune `TOP_K` down
