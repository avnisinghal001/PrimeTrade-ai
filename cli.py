#!/usr/bin/env python3
"""CLI entry point for placing Binance Futures Testnet orders."""
import argparse
import os
import sys
from pathlib import Path

from bot.client import BinanceAPIError, BinanceClient
from bot.logging_config import logger
from bot.orders import build_order_params, place_order
from bot.validators import ValidationError


def load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_credentials() -> tuple[str, str]:
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print(
            "ERROR: Set BINANCE_API_KEY and BINANCE_API_SECRET in PowerShell or in a local .env file.",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key, api_secret


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Place MARKET, LIMIT, and STOP_LIMIT orders on Binance Futures Testnet (USDT-M)."
    )
    parser.add_argument("--interactive", action="store_true", help="Use guided prompts instead of CLI flags")
    parser.add_argument("--symbol", help="Trading pair, e.g. BTCUSDT")
    parser.add_argument("--side", choices=["BUY", "SELL"], help="BUY or SELL")
    parser.add_argument(
        "--type",
        dest="order_type",
        choices=["MARKET", "LIMIT", "STOP_LIMIT"],
        help="Order type: MARKET, LIMIT, or STOP_LIMIT",
    )
    parser.add_argument("--quantity", help="Order quantity")
    parser.add_argument("--price", help="Required for LIMIT and STOP_LIMIT orders")
    parser.add_argument("--stop-price", help="Required for STOP_LIMIT orders")
    return parser


def prompt_text(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} is required.")


def prompt_choice(label: str, choices: list[str]) -> str:
    print(label)
    for index, choice in enumerate(choices, start=1):
        print(f"  {index}. {choice}")

    while True:
        value = input("Choose an option: ").strip().upper()
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return choices[int(value) - 1]
        if value in choices:
            return value
        print(f"Enter one of: {', '.join(choices)}")


def collect_interactive_args(args: argparse.Namespace) -> argparse.Namespace:
    print("\nGuided Order Entry")
    print("------------------")
    args.symbol = prompt_text("Symbol (e.g. BTCUSDT)").upper()
    args.side = prompt_choice("Side", ["BUY", "SELL"])
    args.order_type = prompt_choice("Order type", ["MARKET", "LIMIT", "STOP_LIMIT"])
    args.quantity = prompt_text("Quantity")

    if args.order_type in {"LIMIT", "STOP_LIMIT"}:
        args.price = prompt_text("Limit price")
    else:
        args.price = None

    if args.order_type == "STOP_LIMIT":
        args.stop_price = prompt_text("Stop/trigger price")
    else:
        args.stop_price = None

    return args


def require_direct_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    missing = [
        flag
        for flag, value in {
            "--symbol": args.symbol,
            "--side": args.side,
            "--type": args.order_type,
            "--quantity": args.quantity,
        }.items()
        if value is None
    ]
    if missing:
        parser.error(f"the following arguments are required: {', '.join(missing)}")


def print_order_summary(params: dict, response: dict) -> None:
    print("\nORDER REQUEST SUMMARY")
    print("---------------------")
    for key, value in params.items():
        print(f"{key}: {value}")

    print("\nORDER RESPONSE")
    print("--------------")
    fields = [
        ("orderId", "orderId"),
        ("algoId", "algoId"),
        ("clientAlgoId", "clientAlgoId"),
        ("status", "status"),
        ("algoStatus", "algoStatus"),
        ("orderType", "orderType"),
        ("executedQty", "executedQty"),
        ("avgPrice", "avgPrice"),
        ("triggerPrice", "triggerPrice"),
    ]
    for key, label in fields:
        value = response.get(key)
        if value not in (None, ""):
            print(f"{label}: {value}")

    print("\nSUCCESS: Order placed on Binance Futures Testnet.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.interactive:
        args = collect_interactive_args(args)
    else:
        require_direct_args(parser, args)

    try:
        params = build_order_params(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
        )
    except ValidationError as exc:
        print(f"VALIDATION ERROR: {exc}", file=sys.stderr)
        logger.warning("Validation failed: %s", exc)
        sys.exit(2)

    api_key, api_secret = get_credentials()
    client = BinanceClient(api_key, api_secret)

    print(f"Placing {args.order_type} {params['side']} order for {params['symbol']}...")

    try:
        response = place_order(
            client=client,
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
        )
    except ValidationError as exc:
        print(f"VALIDATION ERROR: {exc}", file=sys.stderr)
        logger.warning("Validation failed: %s", exc)
        sys.exit(2)
    except BinanceAPIError as exc:
        print(f"API ERROR [{exc.code}]: {exc.message}", file=sys.stderr)
        logger.error("API error placing order: %s", exc)
        sys.exit(3)
    except ConnectionError as exc:
        print(f"NETWORK ERROR: {exc}", file=sys.stderr)
        logger.error("Network error: %s", exc)
        sys.exit(4)
    except TimeoutError as exc:
        print(f"TIMEOUT ERROR: {exc}", file=sys.stderr)
        logger.error("Timeout: %s", exc)
        sys.exit(4)
    except Exception as exc:
        print(f"UNEXPECTED ERROR: {exc}", file=sys.stderr)
        logger.exception("Unexpected error placing order")
        sys.exit(5)

    print_order_summary(params, response)


if __name__ == "__main__":
    main()
