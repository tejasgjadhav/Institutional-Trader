"""Holiday-shifted expiries (16-Oct-2026): when Tuesday is an NSE holiday, NIFTY's weekly expiry moves to
Monday. Checks against the LIVE contract master and the NSE holiday file (no orders, no position writes):
each upcoming shifted expiry is detected as an expiry day by the 0DTE scan, the open recorder and the
trading-day check, and the holiday itself is not."""
import sys, os, json
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import engine.zero_dte as Z
import engine.dte_multi as D
import engine.open_recorder as R
import engine.data_utils as DU
from engine.nse_holidays import is_exchange_holiday
from engine.options import _load_index
from engine.instruments import to_instrument_key

FAILED = []
def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(name)

def fake_today(d):
    class FD(date):
        @classmethod
        def today(cls):
            return d
    return FD

uk = to_instrument_key("NIFTY")
nexp = sorted({datetime.fromtimestamp(c["expiry"] / 1000).date() for c in _load_index().get(uk, [])})
years = {int(y) for y in json.load(open(os.path.join(os.path.dirname(Z.__file__), "nse_holidays.json")))["years"]}
shifted = [e for e in nexp if e.weekday() != 1 and e >= date.today() and e.year in years][:4]
print("NIFTY expiries not on a Tuesday:", [f"{e} {e:%a}" for e in shifted])
for e in shifted:
    tue = e + __import__("datetime").timedelta(days=(1 - e.weekday()) % 7)
    check(f"{tue} ({tue:%a}) is an NSE holiday, which is why {e} is the expiry", is_exchange_holiday(tue), True)
    Z.date = fake_today(e)
    check(f"{e} {e:%a}: 0DTE NIFTY sees today's contracts", len(Z._todays_ce_chain()) > 0, True)
    check(f"{e} {e:%a}: PE chain too (FLIP side)", len(Z._todays_chain('PE')) > 0, True)
    check(f"{e} {e:%a}: not a holiday, so the market check passes", is_exchange_holiday(e), False)
    Z.date = fake_today(tue)
    check(f"{tue} {tue:%a} (holiday): no NIFTY expiry contracts", len(Z._todays_ce_chain()), 0)
Z.date = date
sx = sorted({datetime.fromtimestamp(c["expiry"] / 1000).date() for c in D._bse_sensex_options()})
odd = [e for e in sx if e.weekday() != 3 and e >= date.today()]
print("SENSEX expiries not on a Thursday:", [f"{e} {e:%a}" for e in odd] or "none")
for e in odd[:3]:
    D.date = fake_today(e)
    check(f"SENSEX {e} {e:%a}: book sees today's contracts", len(D._chain_today(D.BOOKS[0])) > 0, True)
D.date = date
print(f"\n{'ALL PASS' if not FAILED else f'{len(FAILED)} FAILED: {FAILED}'}")
sys.exit(1 if FAILED else 0)
