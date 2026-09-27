#!/bin/bash
cd /Users/sayali/files/institutional-trader
before=$(wc -l < research/expansion2/legfails.jsonl)
for tp in 0.20 0.30 0.40 0.50 0.60 0.99; do
  for st in main outs p8; do
    .venv/bin/python research/tp_sweep_driver.py $tp $st IS >> research/tpsweep/is.log 2>&1
  done
done
for tp in 0.20 0.30 0.40 0.50 0.60 0.99; do
  for st in main outs p8; do
    .venv/bin/python research/patient_run.py research/tp_sweep_driver.py $tp $st OOS >> research/tpsweep/oos.log 2>&1
  done
done
echo "legfails $(( $(wc -l < research/expansion2/legfails.jsonl) - before ))" > research/tpsweep/done.flag
