#!/bin/bash
cd /Users/sayali/files/institutional-trader
while [ ! -f research/band_retry_done.flag ]; do sleep 60; done
.venv/bin/python research/patient_run.py studies/ndte/build_symbol_history.py OOS > research/symbol_history_build.log 2>&1
.venv/bin/python studies/ndte/build_name_history.py > research/name_history_build.log 2>&1
echo done > research/histories_done.flag
