"""Decode every money-bearing JSON request without binary floating-point loss."""

import json
from decimal import Decimal
from fastapi import Request
from fastapi.routing import APIRoute


class DecimalJSONRequest(Request):
    async def json(self):
        # Preserve decimal JSON numbers before Pydantic sees them.
        def reject_nonfinite(value):
            raise json.JSONDecodeError(
                "Non-finite JSON numbers are not allowed", value, 0
            )

        if not hasattr(self, "_json"):
            self._json = json.loads(
                await self.body(), parse_float=Decimal, parse_constant=reject_nonfinite
            )
        return self._json


class DecimalJSONRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            return await handler(DecimalJSONRequest(request.scope, request.receive))

        return handle
