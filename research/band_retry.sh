#!/bin/bash
cd /Users/sayali/files/institutional-trader
while [ ! -f research/run5_retry_done.flag ]; do sleep 60; done
for n in 2 3 4; do
  before=$(wc -l < research/expansion2/legfails.jsonl)
  PREM=30 .venv/bin/python research/patient_run.py studies/ndte/prem_band25.py OOS > research/premband25_oos_pass$n.log 2>&1
  after=$(wc -l < research/expansion2/legfails.jsonl)
  .venv/bin/python studies/ndte/premband25_screen.py > research/premband25_screen_pass$n.txt 2>&1
  echo "pass $n legfails $((after-before))" >> research/band_retry.log
  if grep -q "saved" research/premband25_oos_pass$n.log && [ $((after-before)) -eq 0 ]; then echo "pass $n clean" > research/band_clean.flag; break; fi
done
echo done > research/band_retry_done.flag
