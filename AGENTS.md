# Repository Guidelines

GraphCoder is a Python 3.13 multi-agent coding system built with LangGraph and LangChain.

## Project Structure & Module Organization

- `main.py` is the entry point; `config.py` holds environment settings; `requirements.txt` lists dependencies; `.env.example` is the config template.
- `src/core/` is for graph and state definitions; `src/agents/` for agents; `src/nodes/` for LangGraph nodes; `src/prompts/` for prompt templates; `src/data/` for I/O; `src/api/` for entry points (CLI); `src/utils/` for shared helpers; `src/tests/` for tests.
- `docs/` contains architecture and agent documentation, including `docs/AGENTS.md` for agent behavior specs; `.github/` holds issue/PR templates and CI.

Keep agent logic under `src/agents/`, node implementations under `src/nodes/`, and prompt templates under `src/prompts/`.

## Build, Test, and Development Commands

```bash
conda create -n graphcoder python=3.13 -y && conda activate graphcoder
pip install -r requirements.txt
cp .env.example .env   # then fill in API keys
python main.py         # run the CLI
ruff check src/        # lint
mypy src/              # type check (best-effort in CI)
pytest src/tests/ -v   # run tests
```

CI uses `uv` to install dependencies and runs Ruff, mypy, pytest, and a TruffleHog secret scan.

## Coding Style & Naming Conventions

- Follow Ruff defaults and keep lines at or under 100 characters.
- Use `PascalCase` for classes, `snake_case` for functions and variables, and `UPPER_SNAKE_CASE` for constants.
- Add type hints to public functions and use Google-style docstrings.
- Use absolute imports from `src.*`, for example `from src.utils.llm import build_llm`; never manipulate `sys.path`.
- Use `src/utils/llm.py:build_llm()` for LLM clients instead of instantiating providers directly.
- Add new environment settings to `config.py`, `.env.example`, and your local `.env`.

## Testing Guidelines

- Use pytest. Place tests in `src/tests/`, name files `test_*.py`, and name functions after behavior, such as `test_build_llm_uses_configured_model`.
- No coverage threshold is enforced, but add focused tests for changed logic; CI skips pytest when no test files exist.

## Commit & Pull Request Guidelines

- Follow Conventional Commits (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`) with an optional scope such as `fix(ci):`; keep commits focused and reference issues with `Closes #12`.
- Pull requests must use the PR template, link issues, pass CI, stay scoped, and complete the checklist.
- Update `CHANGELOG.md`, `docs/`, and `.env.example` when relevant.

## Security & Configuration Tips

- Never commit `.env` or real API keys; keep credentials in environment variables only and derive local config from `.env.example`.
- Run CI's TruffleHog secret scan before requesting review.
