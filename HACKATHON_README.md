# Weaver ⚡️

**Built for the Hackathon using the Nous Research API (Hermes-4-405B)**

## The Problem
Web scrapers and third-party APIs are incredibly fragile. When a target website updates its UI or changes its CSS classes (DOM structure), traditional scrapers break immediately. This causes data loss, downtime, and forces engineers to manually inspect the new HTML and rewrite the code.

## The Solution
**Weaver** is an autonomous, self-healing API generation engine powered by the Nous Research Hermes LLM. It completely automates the creation and maintenance of data pipelines.

It features two core AI workflows:
1. **Zero-to-One Dynamic Generation (`init_api.py`)**: Provide a target URL and a simple description of the data you want. The Hermes *Coder Agent* will fetch the page, understand its structure, and write a full FastAPI web scraper from scratch. The *Inspector Agent* verifies the compilation and fixes any missing imports before saving it.
2. **Zero-Downtime Self Healing (`health_check.py`)**: A background orchestrator continuously monitors your running API. If the target website changes its UI and breaks your API, the orchestrator detects the DOM change, sends the broken code + the new HTML to Hermes, and hot-swaps the newly generated, corrected code into production—without dropping a single request.

## Architecture & Agent Workflows

- **Coder Agent (Hermes-4-405B)**: Analyzes HTML and writes Python/FastAPI code.
- **Inspector Agent (Hermes-4-405B)**: Executes the generated code in an isolated subprocess. If the code crashes (e.g., SyntaxError, missing import), it feeds the traceback back to the Coder Agent for iterative self-correction.
- **Orchestration**: Python scripts managing process lifetimes, DOM diffing, and zero-downtime hot-swapping using `uvicorn --reload`.

## How to Run

### Setup
1. Clone the repository and navigate to the project directory.
2. Ensure you have an active `.venv` inside the `agent/` folder: `python -m venv agent/.venv`
3. Install dependencies: `agent/.venv/bin/pip install -r agent/requirements.txt`
4. Add your Nous API Key to the `.env` file: `NOUS_API_KEY=your_key_here`

### 1. Generating a new API from scratch
To dynamically generate an API for any website, run the CLI tool:
```bash
./agent/.venv/bin/python scripts/init_api.py \
    --url "http://example.com" \
    --schema "Extract all article headlines, dates, and authors."
```
This will autonomously generate `agent/scraper_generated.py`.

### 2. Testing the Self-Healing Demo
To see the system catch a broken scraper and fix it live using the LLM:
```bash
./agent/.venv/bin/python demo_heal.py
```
**What happens in the demo:**
1. A mock website boots up alongside your API.
2. We simulate the target website changing its CSS classes (e.g., `.announcement-card` becomes `.ann-item`).
3. The API breaks and returns a `503 Service Unavailable`.
4. The background health monitor detects the failure, calculates the DOM fingerprint difference, and calls the Hermes API.
5. Hermes rewrites the scraper to use the new CSS selectors while perfectly preserving your Pydantic schemas.
6. The new code is hot-swapped into production. The API recovers autonomously!
