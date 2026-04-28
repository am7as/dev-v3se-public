"""Provider registry. Each module exposes NAME and predict(prompt, **kw)."""
from . import claude_cli, gemini, lmstudio, ollama, openai_api, vllm

_PROVIDERS = {
    openai_api.NAME:   openai_api,
    gemini.NAME:       gemini,
    claude_cli.NAME:   claude_cli,
    lmstudio.NAME:     lmstudio,
    ollama.NAME:       ollama,
    vllm.NAME:         vllm,
}


def get(name: str):
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown provider '{name}'. Known: {sorted(_PROVIDERS)}"
        )


def available() -> list[str]:
    return sorted(_PROVIDERS)
