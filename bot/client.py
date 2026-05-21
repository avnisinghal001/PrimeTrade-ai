"""Thin wrapper around the Binance Futures Testnet REST API."""
import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from .logging_config import logger

BASE_URL = "https://testnet.binancefuture.com"
_TIMEOUT = 10  # seconds
_REDACTED_PARAMS = {"signature"}


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceClient:
    def __init__(self, api_key: str, api_secret: str) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._session = requests.Session()
        self._session.trust_env = False
        self._session.headers.update({"X-MBX-APIKEY": self._api_key})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: "***REDACTED***" if key in _REDACTED_PARAMS else value
            for key, value in params.items()
        }

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Any:
        url = BASE_URL + endpoint
        params = params or {}
        if signed:
            params = self._sign(params)

        logger.debug("REQUEST  %s %s  params=%s", method.upper(), url, self._safe_params(params))
        try:
            resp = self._session.request(method, url, params=params, timeout=_TIMEOUT)
        except requests.ConnectionError as exc:
            logger.error("Network error reaching %s %s", method.upper(), endpoint)
            raise ConnectionError(f"Cannot reach Binance Testnet endpoint {endpoint}: {type(exc).__name__}") from exc
        except requests.Timeout:
            logger.error("Request timed out: %s %s", method.upper(), url)
            raise TimeoutError(f"Request to {url} timed out after {_TIMEOUT}s.")

        logger.debug("RESPONSE %s  body=%s", resp.status_code, resp.text[:500])

        try:
            data = resp.json()
        except ValueError as exc:
            logger.error("Non-JSON response from Binance: status=%s body=%s", resp.status_code, resp.text[:500])
            raise BinanceAPIError(resp.status_code, "Non-JSON response from Binance") from exc

        if resp.status_code >= 400:
            message = data.get("msg", resp.reason) if isinstance(data, dict) else resp.reason
            logger.error("HTTP error %s: %s", resp.status_code, message)
            raise BinanceAPIError(resp.status_code, message)

        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            logger.error("API error %s: %s", data["code"], data.get("msg"))
            raise BinanceAPIError(data["code"], data.get("msg", "Unknown error"))

        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def place_order(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Place a futures order.  kwargs map directly to Binance API params:
          symbol, side, type, quantity, price, timeInForce, etc.
        """
        return self._request("POST", "/fapi/v1/order", params=kwargs, signed=True)

    def place_algo_order(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Place a futures algo order such as STOP_LIMIT.
        """
        return self._request("POST", "/fapi/v1/algoOrder", params=kwargs, signed=True)
