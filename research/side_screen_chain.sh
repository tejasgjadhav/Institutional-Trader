#!/bin/bash
cd /Users/sayali/files/institutional-trader
before=$(wc -l < research/expansion2/legfails.jsonl)
.venv/bin/python research/pruned8.py IS > research/pruned8_is.log 2>&1
.venv/bin/python research/patient_run.py research/pruned8.py OOS > research/pruned8_oos.log 2>&1
.venv/bin/python research/patient_run.py studies/ndte/expand2_oos.py OOS > research/expand2_oos_run5.log 2>&1
after=$(wc -l < research/expansion2/legfails.jsonl)
echo "legfails during chain: $((after-before))" > research/side_screen_chain.done
