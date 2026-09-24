"""The ATS adapters, by source name.

Only the six that need no candidate account will ever appear here. Workday,
Taleo and iCIMS each require creating a login with that employer, and
creating one means accepting their terms as the candidate — which is not
ours to accept. Those rows are refused at enqueue with a message saying so.

LinkedIn, Indeed, Naukri and Dice are not on this list and must never be
added to it. No public apply API, against their terms, and automating them
gets the crawler blocked and the candidate's account with it.
"""
from .base import Adapter, FillResult, Question          # noqa: F401
from .greenhouse import GreenhouseAdapter

# Slice 1 ships one. The other five are the same six methods with different
# selectors; each goes in here as it is written, and nothing else changes.
ADAPTERS = {
    GreenhouseAdapter.source: GreenhouseAdapter,
}


def adapter_for(source):
    """The adapter for a source, or None if we do not drive that one."""
    cls = ADAPTERS.get((source or "").lower())
    return cls() if cls else None
