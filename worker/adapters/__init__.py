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
from .form import FormAdapter                            # noqa: F401
from .greenhouse import GreenhouseAdapter
from .ats import (LeverAdapter, AshbyAdapter, WorkableAdapter,
                  SmartRecruitersAdapter, RecruiteeAdapter)

# All six no-login ATSs. Everything behavioural lives in FormAdapter; each
# of these is the selectors that board uses and the words it says back.
#
# APPLY_DRIVABLE in main.py must list exactly these keys — test_apply_worker
# asserts it, so adding an adapter and forgetting the other edit fails the
# build instead of shipping a queue that accepts what it cannot drive.
ADAPTERS = {
    GreenhouseAdapter.source: GreenhouseAdapter,
    LeverAdapter.source: LeverAdapter,
    AshbyAdapter.source: AshbyAdapter,
    WorkableAdapter.source: WorkableAdapter,
    SmartRecruitersAdapter.source: SmartRecruitersAdapter,
    RecruiteeAdapter.source: RecruiteeAdapter,
}


def adapter_for(source):
    """The adapter for a source, or None if we do not drive that one."""
    cls = ADAPTERS.get((source or "").lower())
    return cls() if cls else None
