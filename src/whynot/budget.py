"""Hard cap on model spend for one command (`create`, `eval`, `validate`, experiments).

Two checks, both needed:

- before running: `Budget.require(estimate)` refuses to start a command whose
  estimated cost is above the cap, so nobody discovers the bill halfway;
- during the run: `ModelClient` calls `check()` before every call and `add()`
  after it. Once spending reaches the cap, no further call is made.

Guarantee: `spent <= max_usd + the cost of the calls already in flight` when
the cap is reached (one call when sequential, at most one per worker thread
when parallel). Calls are billed by the provider after they run, so a single
call cannot be stopped midway.
"""

import math
import threading
from dataclasses import dataclass

from whynot.costs import token_cost


class BudgetExceeded(RuntimeError):
    """The command's model budget is spent (or would be): no further call is made."""


class Budget:
    """Spend tracker with an optional hard cap, safe to share between threads."""

    def __init__(self, max_usd: float | None = None):
        if max_usd is not None and (math.isnan(max_usd) or max_usd < 0):
            raise ValueError(f"budget must be a number >= 0, got {max_usd!r}")
        self.max_usd = max_usd
        self._spent = 0.0
        self._lock = threading.Lock()

    @property
    def spent(self) -> float:
        return self._spent

    @property
    def remaining(self) -> float:
        return math.inf if self.max_usd is None else max(0.0, self.max_usd - self._spent)

    def require(self, estimate_usd: float) -> None:
        """Refuse to start when the estimate is above the cap (checked before any call)."""
        if math.isnan(estimate_usd) or estimate_usd < 0:
            raise ValueError(f"estimate must be a number >= 0, got {estimate_usd!r}")
        if self.max_usd is not None and estimate_usd > self.max_usd:
            raise BudgetExceeded(f"estimated ${estimate_usd:.2f} is above the ${self.max_usd:.2f} cap: "
                                 "lower the size of the run or raise the cap")

    def check(self) -> None:
        """Before a call: stop once the cap is reached."""
        if self.max_usd is not None and self._spent >= self.max_usd:
            raise BudgetExceeded(f"model budget of ${self.max_usd:.2f} spent (${self._spent:.3f})")

    def add(self, usd: float) -> None:
        """After a call: what it cost (always recorded, even past the cap: the provider billed it)."""
        with self._lock:
            self._spent += usd


@dataclass(frozen=True)
class CallEstimate:
    """Expected size of one kind of model call, for estimates before a run."""

    model: str
    input_tokens: int
    output_tokens: int  # reasoning tokens included: they are billed as output
    calls: int = 1

    @property
    def usd(self) -> float:
        return self.calls * token_cost(self.model, self.input_tokens, 0, self.output_tokens)


def estimate_usd(*calls: CallEstimate) -> float:
    """Total of several estimates (no prompt-cache discount: estimates err on the high side)."""
    return sum(c.usd for c in calls)
