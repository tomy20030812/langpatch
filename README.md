# langpatch

Generate a `git apply`-ready patch from a natural language requirement.
- Local CPU embeddings + Chroma index
- DeepSeek API (OpenAI-compatible) for planning and patch generation

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set DEEPSEEK_API_KEY
