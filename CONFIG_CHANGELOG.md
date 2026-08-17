# Config changelog

Every change to a tunable in `engine/config.py`, recorded automatically by
`engine/config_ledger.py` on engine start. Newest first.

**To roll back a change**, `engine/config.py` is git-tracked, so:

```bash
git checkout <the SHA shown below> -- engine/config.py
```

then restart the engine. The ledger never rewrites config itself — auto-editing a live
trading config is a worse failure mode than the one it would prevent.

---

## 2026-08-17 16:18:41 IST

commit at snapshot: `6847419 (UNCOMMITTED EDITS)` — OI floor is exactly 5 lots, not max(100, 5*lot)

| tunable | before | after |
|---|---|---|
| `STOCK_CREDIT_MIN_OI_LOTS` | `5` | `1` |

Roll back with: `git checkout 6847419 (UNCOMMITTED EDITS) -- engine/config.py`

---

## 2026-08-17 15:52:43 IST

commit at snapshot: `5b32263 (UNCOMMITTED EDITS)` — studies: final IS+OOS+ROM after six corrections, with the convergence caveat

| tunable | before | after |
|---|---|---|
| `STOCK_CREDIT_MIN_OI_LOTS` | `10` | `5` |

Roll back with: `git checkout 5b32263 (UNCOMMITTED EDITS) -- engine/config.py`

---

## 2026-08-17 10:49:38 IST

commit at snapshot: `182f4d4 (UNCOMMITTED EDITS)` — ui: fix f-string escape that broke the viewer, tidy duplicate audit card

| tunable | before | after |
|---|---|---|
| `STOCK_CREDIT_MIN_OI_LOTS` | `"\u2205"` | `10` |

Roll back with: `git checkout 182f4d4 (UNCOMMITTED EDITS) -- engine/config.py`

---

## 2026-08-06 11:07:10 IST

commit at snapshot: `60b274f (UNCOMMITTED EDITS)` — ui: the watchlist empty-state said 'engine builds it at 3:05 PM' — two retimings stale

| tunable | before | after |
|---|---|---|
| `WATCHLIST_DIGEST_AT` | `"\u2205"` | `"15:31"` |

Roll back with: `git checkout 60b274f (UNCOMMITTED EDITS) -- engine/config.py`

---

