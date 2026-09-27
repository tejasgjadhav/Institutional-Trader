#!/bin/bash
cd /Users/sayali/files/institutional-trader
for n in 2 3 4; do
  .venv/bin/python research/patient_run.py studies/ndte/deployed_backtest.py OOS > research/run5_oos_pass$n.log 2>&1
  if grep -q "DONE-OOS" research/run5_oos_pass$n.log && ! grep -qE "FETCH INTEGRITY: [1-9]|fetch\(es\) failed" research/run5_oos_pass$n.log; then
    echo "pass $n clean" > research/run5_clean.flag; break
  fi
done
echo "retries finished" > research/run5_retry_done.flag
