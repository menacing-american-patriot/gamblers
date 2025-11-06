from typing import Optional

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType

from .config import Settings


class ExecutionService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = self._create_client()
        self.trading_enabled = False
        self._creds_error_emitted = False
        self._configure_api_credentials()

    def _create_client(self) -> ClobClient:
        if self.settings.private_key:
            kwargs = {
                "chain_id": self.settings.chain_id,
                "key": self.settings.private_key,
            }
            if self.settings.signature_type:
                kwargs["signature_type"] = self.settings.signature_type
            if self.settings.funder_address:
                kwargs["funder"] = self.settings.funder_address
            return ClobClient(self.settings.clob_host, **kwargs)
        return ClobClient(self.settings.clob_host)

    def _configure_api_credentials(self):
        import os

        api_key = os.getenv("POLY_API_KEY") or os.getenv("CLOB_API_KEY")
        api_secret = os.getenv("POLY_API_SECRET") or os.getenv("CLOB_API_SECRET")
        api_passphrase = os.getenv("POLY_API_PASSPHRASE") or os.getenv("CLOB_API_PASSPHRASE")

        if api_key and api_secret and api_passphrase:
            creds = ApiCreds(
                api_key=api_key,
                api_secret=api_secret,
                api_passphrase=api_passphrase,
            )
            self.client.set_api_creds(creds)
            self.trading_enabled = True
        else:
            self.trading_enabled = False

    def refresh_credentials(self):
        self._configure_api_credentials()

    def ensure_trading_enabled(self, logger) -> bool:
        if self.trading_enabled:
            return True
        if not self._creds_error_emitted:
            logger.error(
                "API credentials missing; set POLY_API_KEY, POLY_API_SECRET, and POLY_API_PASSPHRASE to enable trading"
            )
            self._creds_error_emitted = True
        return False

    def place_order(
        self,
        *,
        token_id: str,
        side: str,
        amount: float,
        price: float,
        logger,
    ) -> bool:
        if not self.ensure_trading_enabled(logger):
            return False

        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=amount / price,
            side=side,
            fee_rate_bps=0,
        )

        signed_order = self.client.create_order(order_args)
        response = self.client.post_order(signed_order, OrderType.GTC)
        if response and response.get("success"):
            logger.info(
                f"✓ Placed {side} bet: ${amount:.2f} @ {price:.3f} on {token_id[:8]}..."
            )
            return True
        logger.warning(f"Order placement failed: {response}")
        return False
