"""The notices this edition carries, in one place.

This is the reader edition of the system from *The Algo Trading Bible*. It is the machine,
not the author's strategy. The strategies he actually trades are not in this repository in
any form: not behind a blank, not described in a comment, not hinted at in a file name.

What ships is a worked example built on VWAP, written out in full in engine/example_vwap.py.
It runs end to end so you can see how the parts fit. It has never been backtested and it is
not recommended. Read the book, do your own research, and write your own book beside it.
"""
import logging

log = logging.getLogger(__name__)

DISCLAIMER = (
    "READER EDITION. This is study code published alongside the book The Algo Trading Bible. "
    "It is not investment advice, not a recommendation and not a signal service. The one "
    "strategy that ships with it is a teaching example that has never been backtested or "
    "validated, and the author does not trade it. The stock list is every NSE F&O stock, not "
    "a selection; choose and test your own. If you run this, or act on anything it prints, "
    "that is your decision and your risk alone. Tejas Jadhav accepts no responsibility and no "
    "liability for any trade you place or any loss you suffer. Speak to a licensed advisor "
    "before you trade.")

# Kept under its old name so older scripts and notes still import cleanly.
GATES_DISCLAIMER = DISCLAIMER

NOTICE = ("study code from The Algo Trading Bible — the example strategy is untested, "
          "see DISCLAIMER.md")


def stand_down(book: str, reason) -> list:
    """Log once that a book cannot trade, and return an empty signal list.

    The caller returns this straight to the scanner, so the scan completes normally and the
    dashboard reports no signal.
    """
    if book not in _announced:
        _announced.add(book)
        detail = ", ".join(sorted(reason)) if not isinstance(reason, str) else reason
        log.warning("%s stands down: %s. %s", book, detail or "(unspecified)", NOTICE)
    return []


_announced = set()
