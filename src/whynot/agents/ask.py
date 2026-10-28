"""Ask a model for structured JSON, validate it, and repair it with feedback.

Every agent uses `ask_json`: the answer is parsed and passed to a `validate`
function that either returns a typed result or raises `Invalid` with a message
saying exactly what is wrong. On failure the model gets its own answer back
with the error and is asked for a corrected version, up to `repairs` times.
Nothing is guessed: if it is still invalid, `AgentError` is raised with every
error seen, and the spend is still recorded by the model client.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from whynot.jsonio import JSONExtractError, extract_json


class Invalid(ValueError):
    """Raised by validators: the message is sent back to the model."""


class AgentError(RuntimeError):
    def __init__(self, message: str, errors: list[str], usd: float):
        super().__init__(message)
        self.errors = errors
        self.usd = usd


class ChatClient(Protocol):
    def chat(self, messages: list[dict], *, module: str, model: str = ..., **kwargs: Any) -> Any: ...


@dataclass
class Answer[T]:
    value: T
    usd: float
    attempts: int
    raw: Any  # the parsed JSON, kept for the run's audit trail


def ask_json[T](client: ChatClient, messages: list[dict[str, Any]], validate: Callable[[Any], T], *, module: str,
             model: str, repairs: int = 2, **kwargs: Any) -> Answer[T]:
    history = list(messages)
    errors: list[str] = []
    usd = 0.0
    for attempt in range(1, repairs + 2):
        result = client.chat(history, module=module, model=model, **kwargs)
        usd += result.cost.usd
        try:
            data = extract_json(result.text)
            return Answer(validate(data), usd, attempt, data)
        except (JSONExtractError, Invalid) as exc:
            errors.append(str(exc))
            history = [*history, {"role": "assistant", "content": result.text[:6000]},
                       {"role": "user", "content": f"Your answer is invalid: {exc}\n"
                                                   "Reply with the corrected JSON only, same schema."}]
    raise AgentError(f"{module}: no valid answer after {repairs + 1} attempts: {errors[-1]}", errors, usd)
