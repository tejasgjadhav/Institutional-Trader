#!/usr/bin/env python3
"""Launcher for the desktop viewer.

  python main.py             open the dashboard
  python main.py --status    print the paper book and exit

The dashboard is read-only. To run the engine, which is the part that scans and books, use:

  python -m engine.engine_runner          run it
  python -m engine.engine_runner --once   run one cycle and stop

Study code. Not investment advice. See DISCLAIMER.md.
"""
import os
import argparse

os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true", help="print the paper book and exit")
    args = parser.parse_args()

    if args.status:
        from engine.agent import Agent
        Agent().trade_log.print_status()
    else:
        from engine.ui_terminal import run
        run()
