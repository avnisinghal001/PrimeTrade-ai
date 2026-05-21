#!/usr/bin/env python3
"""Lightweight local web UI for the Binance Futures Testnet trading bot."""
import html
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from bot.logging_config import logger
from bot.client import BinanceAPIError, BinanceClient
from bot.orders import build_order_params, place_order
from bot.validators import ValidationError
from cli import load_dotenv


HOST = "127.0.0.1"
PORT = 8000


def get_credentials() -> tuple[str, str]:
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise RuntimeError("Set BINANCE_API_KEY and BINANCE_API_SECRET in PowerShell or .env.")
    return api_key, api_secret


def field_value(fields: dict[str, list[str]], name: str) -> str | None:
    value = fields.get(name, [""])[0].strip()
    return value or None


def explain_error(exc: Exception, order_args: dict[str, str | None]) -> str:
    message = str(exc)
    lower_message = message.lower()

    if "would immediately trigger" in lower_message:
        if order_args.get("order_type") == "STOP_LIMIT":
            side = order_args.get("side")
            if side == "SELL":
                return (
                    "Your SELL STOP_LIMIT would trigger immediately. Use a stop/trigger price below "
                    "the current market price, and set the limit price at or below the trigger price."
                )
            if side == "BUY":
                return (
                    "Your BUY STOP_LIMIT would trigger immediately. Use a stop/trigger price above "
                    "the current market price, and set the limit price at or above the trigger price."
                )
        return "The stop/trigger price is already crossed by the current market price."

    if "limit price can't be higher" in lower_message:
        return f"Binance rejected the limit price: {message}"

    if "insufficient" in lower_message or "margin" in lower_message:
        return "Binance rejected the order because the testnet account does not have enough available balance or margin."

    if isinstance(exc, ConnectionError):
        return "Network error: the app could not reach Binance Testnet. Check internet access and try again."

    if isinstance(exc, TimeoutError):
        return "Timeout error: Binance Testnet did not respond in time. Try again."

    if isinstance(exc, ValidationError):
        return message

    if isinstance(exc, BinanceAPIError):
        return f"Binance API error: {exc.message}"

    return message


def render_page(
    message: str = "",
    details: str = "",
    response: dict | None = None,
    form: dict[str, str | None] | None = None,
    is_error: bool = False,
) -> str:
    form = form or {}
    symbol = html.escape(form.get("symbol") or "BTCUSDT")
    side = form.get("side") or "BUY"
    order_type = form.get("order_type") or "MARKET"
    quantity = html.escape(form.get("quantity") or "0.001")
    price = html.escape(form.get("price") or "")
    stop_price = html.escape(form.get("stop_price") or "")

    response_html = ""
    if response:
        rows = "\n".join(
            f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
            for key, value in response.items()
            if value not in (None, "")
        )
        response_html = f"""
        <section class="panel response-panel">
          <h2>Order Response</h2>
          <table>{rows}</table>
        </section>
        """

    message_class = "message error" if is_error else "message success"
    detail_html = f"<span>{html.escape(details)}</span>" if details else ""
    message_html = (
        f"<div class='{message_class}'><strong>{html.escape(message)}</strong>{detail_html}</div>"
        if message
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Bot UI</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --surface: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #d8dee9;
      --accent: #136f63;
      --accent-strong: #0f5a51;
      --danger: #b42318;
      --success-bg: #e8f6ef;
      --error-bg: #fdecec;
      --warning: #b7791f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Arial, sans-serif;
      line-height: 1.4;
    }}
    main {{
      width: min(960px, calc(100% - 32px));
      margin: 32px auto;
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }}
    h1 {{ margin: 0; font-size: 26px; }}
    h2 {{ margin: 0 0 16px; font-size: 18px; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--muted);
      background: var(--surface);
      font-size: 13px;
      white-space: nowrap;
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      box-shadow: 0 8px 24px rgba(23, 32, 51, 0.06);
    }}
    form {{ display: grid; gap: 16px; }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    label {{ display: grid; gap: 7px; font-weight: 700; font-size: 14px; }}
    input, select, button {{
      width: 100%;
      min-height: 42px;
      font: inherit;
      padding: 10px 12px;
      border: 1px solid #b9c2d0;
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
    }}
    input:disabled {{
      color: #98a2b3;
      background: #f1f3f6;
    }}
    button {{
      border-color: var(--accent);
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }}
    button:hover {{ background: var(--accent-strong); }}
    .message {{
      display: grid;
      gap: 6px;
      margin: 0 0 16px;
      padding: 12px 14px;
      border-radius: 6px;
      border: 1px solid var(--line);
    }}
    .message strong {{ font-size: 16px; }}
    .message span {{ font-weight: 500; }}
    .success {{ background: var(--success-bg); color: var(--accent-strong); }}
    .error {{ background: var(--error-bg); color: var(--danger); }}
    .response-panel {{ margin-top: 18px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; }}
    th {{ width: 190px; color: var(--muted); font-weight: 700; }}
    tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
    @media (max-width: 680px) {{
      main {{ width: min(100% - 20px, 960px); margin: 18px auto; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .form-grid {{ grid-template-columns: 1fr; }}
      .panel {{ padding: 16px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Trading Bot Console</h1>
      <span class="badge">Binance Futures Testnet</span>
    </header>
    {message_html}
    <section class="panel">
      <h2>New Order</h2>
      <form method="post">
        <div class="form-grid">
          <label>Symbol
            <input name="symbol" value="{symbol}" required>
          </label>
          <label>Side
            <select name="side">
              <option {"selected" if side == "BUY" else ""}>BUY</option>
              <option {"selected" if side == "SELL" else ""}>SELL</option>
            </select>
          </label>
          <label>Order Type
            <select name="order_type" id="orderType">
              <option {"selected" if order_type == "MARKET" else ""}>MARKET</option>
              <option {"selected" if order_type == "LIMIT" else ""}>LIMIT</option>
              <option {"selected" if order_type == "STOP_LIMIT" else ""}>STOP_LIMIT</option>
            </select>
          </label>
          <label>Quantity
            <input name="quantity" value="{quantity}" required>
          </label>
          <label>Limit Price
            <input name="price" id="price" value="{price}" placeholder="LIMIT and STOP_LIMIT">
          </label>
          <label>Stop / Trigger Price
            <input name="stop_price" id="stopPrice" value="{stop_price}" placeholder="STOP_LIMIT only">
          </label>
        </div>
        <button type="submit">Place Order</button>
      </form>
    </section>
    {response_html}
  </main>
  <script>
    const orderType = document.getElementById('orderType');
    const price = document.getElementById('price');
    const stopPrice = document.getElementById('stopPrice');
    function syncFields() {{
      const type = orderType.value;
      price.disabled = type === 'MARKET';
      stopPrice.disabled = type !== 'STOP_LIMIT';
      if (price.disabled) price.value = '';
      if (stopPrice.disabled) stopPrice.value = '';
    }}
    orderType.addEventListener('change', syncFields);
    syncFields();
  </script>
</body>
</html>"""


class TradingBotHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)

    def do_GET(self) -> None:
        print("UI request: GET /", flush=True)
        self.respond(render_page())

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"))
        order_args = {
            "symbol": field_value(fields, "symbol"),
            "side": field_value(fields, "side"),
            "order_type": field_value(fields, "order_type"),
            "quantity": field_value(fields, "quantity"),
            "price": field_value(fields, "price"),
            "stop_price": field_value(fields, "stop_price"),
        }
        print(
            "UI request: POST order "
            f"symbol={order_args['symbol']} side={order_args['side']} "
            f"type={order_args['order_type']} quantity={order_args['quantity']}",
            flush=True,
        )

        try:
            params = build_order_params(**order_args)
            api_key, api_secret = get_credentials()
            client = BinanceClient(api_key, api_secret)
            response = place_order(client=client, **order_args)
            print(
                "UI success: "
                f"orderId={response.get('orderId')} algoId={response.get('algoId')} "
                f"status={response.get('status') or response.get('algoStatus')}",
                flush=True,
            )
            page = render_page(
                "Order submitted successfully.",
                f"{params['side']} {order_args['order_type']} order was accepted by Binance Futures Testnet.",
                response,
                order_args,
            )
        except (ValidationError, BinanceAPIError, ConnectionError, TimeoutError, RuntimeError) as exc:
            friendly_error = explain_error(exc, order_args)
            print(f"UI error: {type(exc).__name__}: {friendly_error}", flush=True)
            print(f"UI raw error: {exc}", flush=True)
            logger.error("UI order error: %s: %s", type(exc).__name__, friendly_error)
            page = render_page("Order failed.", friendly_error, form=order_args, is_error=True)

        self.respond(page)

    def respond(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    server = HTTPServer((HOST, PORT), TradingBotHandler)
    print(f"Trading bot UI running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
