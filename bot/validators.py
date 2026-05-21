from decimal import Decimal, InvalidOperation
from typing import Optional


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}


class ValidationError(ValueError):
    pass


def validate_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s or not s.isalnum():
        raise ValidationError(f"Invalid symbol '{symbol}'. Must be alphanumeric (e.g. BTCUSDT).")
    return s


def validate_side(side: str) -> str:
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValidationError(f"Invalid side '{side}'. Must be one of: {', '.join(VALID_SIDES)}.")
    return s


def validate_order_type(order_type: str) -> str:
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{order_type}'. Must be one of: {', '.join(VALID_ORDER_TYPES)}."
        )
    return t


def validate_quantity(quantity: str) -> str:
    try:
        q = Decimal(str(quantity))
    except InvalidOperation:
        raise ValidationError(f"Invalid quantity '{quantity}'. Must be a positive number.")
    if q <= 0:
        raise ValidationError(f"Quantity must be greater than 0, got {q}.")
    return str(q)


def validate_price(price: Optional[str], order_type: str) -> Optional[str]:
    if order_type in {"LIMIT", "STOP_LIMIT"} and price is None:
        raise ValidationError(f"Price is required for {order_type} orders.")
    if order_type == "MARKET" and price is not None:
        raise ValidationError("Price should only be provided for LIMIT or STOP_LIMIT orders.")
    if price is None:
        return None
    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValidationError(f"Invalid price '{price}'. Must be a positive number.")
    if p <= 0:
        raise ValidationError(f"Price must be greater than 0, got {p}.")
    return str(p)


def validate_stop_price(stop_price: Optional[str], order_type: str) -> Optional[str]:
    if order_type == "STOP_LIMIT" and stop_price is None:
        raise ValidationError("Stop price is required for STOP_LIMIT orders.")
    if order_type != "STOP_LIMIT" and stop_price is not None:
        raise ValidationError("Stop price should only be provided for STOP_LIMIT orders.")
    if stop_price is None:
        return None
    try:
        sp = Decimal(str(stop_price))
    except InvalidOperation:
        raise ValidationError(f"Invalid stop price '{stop_price}'. Must be a positive number.")
    if sp <= 0:
        raise ValidationError(f"Stop price must be greater than 0, got {sp}.")
    return str(sp)
