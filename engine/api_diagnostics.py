"""
API Diagnostics — Test all data sources
Upstox FNO, 5-min candles, NSE API, Yahoo, VIX
"""
import logging
from datetime import datetime
from engine.config import UPSTOX_ANALYTICS_TOKEN
from engine.data_fetcher import (
    fetch_upstox_ltp, fetch_upstox_intraday, fetch_upstox_historical,
    fetch_historical, get_cached_vix, get_cached_nifty_pct
)

logger = logging.getLogger(__name__)


class APIValidator:
    """Comprehensive API health check"""

    def __init__(self):
        self.results = {}
        self.timestamp = datetime.now().isoformat()

    def test_upstox_token(self) -> dict:
        """Verify Upstox token is valid"""
        result = {
            "name": "Upstox Analytics Token",
            "status": "unknown",
            "message": "",
            "details": {}
        }

        if not UPSTOX_ANALYTICS_TOKEN:
            result["status"] = "FAIL"
            result["message"] = "Token not configured in .env"
            return result

        # Check token format
        parts = UPSTOX_ANALYTICS_TOKEN.split(".")
        if len(parts) != 3:
            result["status"] = "FAIL"
            result["message"] = "Token format invalid (JWT should have 3 parts)"
            return result

        result["status"] = "PASS"
        result["message"] = "Token configured and valid format"
        result["details"] = {
            "token_length": len(UPSTOX_ANALYTICS_TOKEN),
            "token_preview": UPSTOX_ANALYTICS_TOKEN[:20] + "..." + UPSTOX_ANALYTICS_TOKEN[-10:],
            "expires": "Feb 2027 (approx)"
        }
        return result

    def test_upstox_ltp(self) -> dict:
        """Test Upstox LTP (last traded price) for equity"""
        result = {
            "name": "Upstox LTP (Equity)",
            "status": "unknown",
            "message": "",
            "details": {}
        }

        try:
            response = fetch_upstox_ltp("INFY.NS")
            if response["success"]:
                result["status"] = "PASS"
                result["message"] = "Live price fetch working"
                result["details"] = {
                    "ticker": "INFY.NS",
                    "price": response["price"],
                    "timestamp": response["timestamp"]
                }
            else:
                result["status"] = "FAIL"
                result["message"] = f"API error: {response['error']}"
        except Exception as e:
            result["status"] = "FAIL"
            result["message"] = str(e)

        return result

    def test_upstox_5min_candles(self) -> dict:
        """Test Upstox 5-min OHLCV candles"""
        result = {
            "name": "Upstox 5-min Candles",
            "status": "unknown",
            "message": "",
            "details": {}
        }

        try:
            # Intraday is empty when market closed — verify via historical instead.
            # Minute data has a limited date range, so request only recent sessions.
            from datetime import datetime, timedelta
            to_d = datetime.now().strftime("%Y-%m-%d")
            from_d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            df = fetch_upstox_historical("INFY.NS", unit="minutes", interval=5,
                                         from_date=from_d, to_date=to_d)
            if not df.empty:
                result["status"] = "PASS"
                result["message"] = "5-min candles fetch working"
                result["details"] = {
                    "ticker": "INFY.NS",
                    "candles_received": len(df),
                    "latest_close": float(df["Close"].iloc[-1]),
                    "latest_time": str(df.index[-1]),
                    "columns": list(df.columns)
                }
            else:
                result["status"] = "FAIL"
                result["message"] = "No candle data returned"
        except Exception as e:
            result["status"] = "FAIL"
            result["message"] = str(e)

        return result

    def test_index_data(self) -> dict:
        """Test Upstox index data (Nifty, BankNifty, VIX)"""
        result = {
            "name": "Upstox Index Data (Nifty/BankNifty/VIX)",
            "status": "unknown",
            "message": "",
            "details": {}
        }

        try:
            nifty = fetch_upstox_historical("NIFTY", unit="days", interval=1)
            bank = fetch_upstox_historical("BANKNIFTY", unit="days", interval=1)
            vix = fetch_upstox_historical("VIX", unit="days", interval=1)

            if not nifty.empty and not bank.empty and not vix.empty:
                result["status"] = "PASS"
                result["message"] = "Index data fetch working"
                result["details"] = {
                    "nifty_close": float(nifty["Close"].iloc[-1]),
                    "banknifty_close": float(bank["Close"].iloc[-1]),
                    "vix_close": float(vix["Close"].iloc[-1]),
                }
            else:
                result["status"] = "FAIL"
                result["message"] = "One or more indices returned no data"
        except Exception as e:
            result["status"] = "FAIL"
            result["message"] = str(e)

        return result

    def test_nse_api_integration(self) -> dict:
        """Test NSE API (options chain, PCR, etc.)"""
        result = {
            "name": "NSE API (Options Chain, PCR, etc)",
            "status": "unknown",
            "message": "",
            "details": {}
        }

        # NSE API would require separate integration
        # For now, testing structure is in place
        result["status"] = "PENDING"
        result["message"] = "NSE API integration requires separate endpoint"
        result["details"] = {
            "planned": ["Options chain", "PCR ratio", "Max pain", "Corporate filings"],
            "requires": "NSE API key / web scraping"
        }

        return result

    def test_historical(self) -> dict:
        """Test daily historical data (Upstox V3)"""
        result = {
            "name": "Upstox Daily Historical",
            "status": "unknown",
            "message": "",
            "details": {}
        }

        try:
            df = fetch_historical("TCS.NS", days=400)
            if not df.empty:
                result["status"] = "PASS"
                result["message"] = "Daily historical data working (Upstox V3)"
                result["details"] = {
                    "ticker": "TCS.NS",
                    "days_fetched": len(df),
                    "date_range": f"{df.index[0].date()} to {df.index[-1].date()}",
                    "latest_close": float(df["Close"].iloc[-1]),
                    "columns": list(df.columns)
                }
            else:
                result["status"] = "FAIL"
                result["message"] = "No historical data returned"
        except Exception as e:
            result["status"] = "FAIL"
            result["message"] = str(e)

        return result

    def test_vix_data(self) -> dict:
        """Test VIX data (India VIX)"""
        result = {
            "name": "VIX Data (^INDIAVIX)",
            "status": "unknown",
            "message": "",
            "details": {}
        }

        try:
            vix = get_cached_vix()
            if vix > 0:
                result["status"] = "PASS"
                result["message"] = "VIX data fetch working"
                result["details"] = {
                    "ticker": "^INDIAVIX",
                    "level": vix,
                    "signal": "Low volatility" if vix < 15 else ("Normal" if vix < 18 else "High volatility")
                }
            else:
                result["status"] = "FAIL"
                result["message"] = "VIX returned zero or invalid"
        except Exception as e:
            result["status"] = "FAIL"
            result["message"] = str(e)

        return result

    def test_nifty_trend(self) -> dict:
        """Test Nifty trend (% from open)"""
        result = {
            "name": "Nifty Trend (% from open)",
            "status": "unknown",
            "message": "",
            "details": {}
        }

        try:
            pct = get_cached_nifty_pct()
            result["status"] = "PASS"
            result["message"] = "Nifty trend fetch working"
            result["details"] = {
                "ticker": "^NSEI",
                "pct_from_open": pct,
                "signal": "Positive" if pct > 0 else ("Negative" if pct < 0 else "Flat")
            }
        except Exception as e:
            result["status"] = "FAIL"
            result["message"] = str(e)

        return result

    def run_all_tests(self) -> dict:
        """Run all API tests"""
        print("\n" + "="*70)
        print("API DIAGNOSTICS — COMPREHENSIVE DATA SOURCE CHECK")
        print("="*70)

        tests = [
            self.test_upstox_token,
            self.test_upstox_ltp,
            self.test_upstox_5min_candles,
            self.test_index_data,
            self.test_historical,
            self.test_vix_data,
            self.test_nifty_trend,
            self.test_nse_api_integration,
        ]

        results = {}
        for test in tests:
            result = test()
            results[result["name"]] = result
            self._print_result(result)

        print("\n" + "="*70)
        self._print_summary(results)
        print("="*70 + "\n")

        return results

    def _print_result(self, result: dict):
        """Print single test result"""
        status_icon = "✓" if result["status"] == "PASS" else ("✗" if result["status"] == "FAIL" else "⊘")
        status_color = "\033[92m" if result["status"] == "PASS" else ("\033[91m" if result["status"] == "FAIL" else "\033[93m")
        reset_color = "\033[0m"

        print(f"\n{status_color}{status_icon} {result['name']}{reset_color}")
        print(f"   Status:  {result['status']}")
        print(f"   Message: {result['message']}")

        if result["details"]:
            print("   Details:")
            for key, value in result["details"].items():
                if isinstance(value, (list, dict)):
                    print(f"     {key}: {value}")
                else:
                    print(f"     {key}: {value}")

    def _print_summary(self, results: dict):
        """Print overall summary"""
        pass_count = sum(1 for r in results.values() if r["status"] == "PASS")
        fail_count = sum(1 for r in results.values() if r["status"] == "FAIL")
        pending_count = sum(1 for r in results.values() if r["status"] == "PENDING")
        total = len(results)

        print(f"\nSUMMARY")
        print(f"  ✓ PASS:    {pass_count}/{total}")
        print(f"  ✗ FAIL:    {fail_count}/{total}")
        print(f"  ⊘ PENDING: {pending_count}/{total}")

        if pass_count >= total - 2:
            print(f"\n✅ API STATUS: OPERATIONAL (Most sources working)")
        elif pass_count >= total // 2:
            print(f"\n⚠️ API STATUS: DEGRADED (Fallbacks available)")
        else:
            print(f"\n❌ API STATUS: CRITICAL (Network/service issues)")


def diagnose():
    """Run full diagnostics"""
    validator = APIValidator()
    return validator.run_all_tests()


if __name__ == "__main__":
    diagnose()
