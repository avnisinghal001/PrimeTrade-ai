"""Order placement logic between the client and the CLI."""
from typing import Any, Dict, Optional

from .client import BinanceClient
from .logging_config import logger
from .validators import (
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)


def build_order_params(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
) -> Dict[str, Any]:
    symbol = validate_symbol(symbol)
    side = validate_side(side)
    order_type = validate_order_type(order_type)
    quantity = validate_quantity(quantity)
    price = validate_price(price, order_type)
    stop_price = validate_stop_price(stop_price, order_type)

    params: Dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": quantity,
        "newOrderRespType": "RESULT",
    }

    if order_type in {"LIMIT", "STOP_LIMIT"}:
        params["price"] = price
        params["timeInForce"] = "GTC"

    if order_type == "STOP_LIMIT":
        params["algoType"] = "CONDITIONAL"
        params["type"] = "STOP"
        params["triggerPrice"] = stop_price

    return params


def place_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
) -> Dict[str, Any]:
    params = build_order_params(symbol, side, order_type, quantity, price, stop_price)
    logger.info(
        "Placing %s %s order | symbol=%s qty=%s price=%s stopPrice=%s",
        side,
        order_type,
        symbol,
        quantity,
        price,
        stop_price,
    )
    if order_type == "STOP_LIMIT":
        response = client.place_algo_order(**params)
    else:
        response = client.place_order(**params)
    logger.info(
        "Order placed | orderId=%s algoId=%s status=%s executedQty=%s avgPrice=%s",
        response.get("orderId"),
        response.get("algoId"),
        response.get("status"),
        response.get("executedQty"),
        response.get("avgPrice"),
    )
    return response
