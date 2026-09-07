"""Service boundary for selecting configured upstream modules."""

from enum import StrEnum

import httpx

from ..clients.http import UpstreamHttpClient
from ..core.config import Settings


class UpstreamModule(StrEnum):
    """Known PubTube module configuration keys."""

    MODULE1 = "module1"
    MODULE2 = "module2"
    MODULE3 = "module3"


class UpstreamService:
    """Expose configured upstream clients without creating public proxy routes."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        timeout: httpx.Timeout,
        config: Settings,
    ) -> None:
        self._client = client
        self._timeout = timeout
        self._urls = {
            UpstreamModule.MODULE1: config.module1_url,
            UpstreamModule.MODULE2: config.module2_url,
            UpstreamModule.MODULE3: config.module3_url,
        }

    def client_for(self, module: UpstreamModule) -> UpstreamHttpClient:
        """Return a reusable client for a known module.

        Args:
            module: Module whose configured base URL should be selected.

        Returns:
            An HTTP client restricted to the selected module base URL.
        """

        return UpstreamHttpClient(
            module=module.value,
            base_url=self._urls[module],
            client=self._client,
            timeout=self._timeout,
        )
