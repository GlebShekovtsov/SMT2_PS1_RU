"""RU fork: shared bookkeeping of every fixed-size allocation in the build.

capacity(name, used, alloc) records usage.  Normally an overflow aborts the
build; with REPORT_ONLY = True (ru/check.py) it is recorded and the caller
truncates/skips so the trial build can report every table in one pass.
"""
REPORT_ONLY = False
CAPACITY = {}


def capacity(name, used, alloc):
    CAPACITY[name] = (used, alloc)
    if used > alloc:
        if REPORT_ONLY:
            return True
        raise SystemExit(f"{name} OVERFLOW {used}>{alloc} (+{used - alloc} bytes)")
    return False
