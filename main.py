#!/usr/bin/env python3
"""
Institutional Trader — Desktop App Launcher
3-Family Alpha NSE Intraday Paper Trading System

Entry point for launchd (auto-start 9:00 AM):
  launchctl load ~/Library/LaunchAgents/com.sayali.institutionaltrader.plist
  launchctl unload ~/Library/LaunchAgents/com.sayali.institutionaltrader.plist

Manual run:
  cd /Users/sayali/files/institutional-trader
  python main.py                 # Launch desktop app (default)
  python main.py --cli           # CLI mode (single scan)
  python main.py --loop          # CLI mode (continuous)
  python main.py --status        # Print stats only
"""
import sys
import os

# Set working directory to institutional-trader
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Run the app
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true", help="CLI mode (single scan)")
    parser.add_argument("--loop", action="store_true", help="CLI mode (continuous loop)")
    parser.add_argument("--status", action="store_true", help="Print stats only")
    args = parser.parse_args()

    if args.status:
        from engine.agent import Agent
        agent = Agent()
        agent.trade_log.print_status()
    elif args.cli or args.loop:
        from engine.agent import Agent
        agent = Agent()
        if args.loop:
            agent.run_continuous()
        else:
            agent.run_once()
    else:
        # Default: launch dark terminal desktop app
        from engine.ui_terminal import main
        main()
