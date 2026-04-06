from __future__ import annotations

from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=16)
def load_prompt_template(name: str) -> str:
    return files(__package__).joinpath(name).read_text(encoding="utf-8").strip()


def render_prompt_template(name: str, **values: str) -> str:
    prompt = load_prompt_template(name)
    for key, value in values.items():
        prompt = prompt.replace(f"{{{{ {key} }}}}", value)
    return prompt
