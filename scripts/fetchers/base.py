"""Abstract base class for data source fetchers."""

from abc import ABC, abstractmethod


class BaseFetcher(ABC):
    """Abstract base class defining the unified fetcher interface.

    Each data source (EastMoney, Sina, Tencent) must implement all methods.
    """

    @property
    @abstractmethod
    def source(self) -> str:
        """Human-readable source name, e.g. 'eastmoney', 'sina'."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Test if this data source is reachable (ping a lightweight endpoint)."""
        ...

    @abstractmethod
    def fetch_business(self, code: str) -> dict | None:
        """Fetch company overview: name, industry, business description.

        Returns:
            {code, name, industry, business} or None if failed
        """
        ...

    @abstractmethod
    def fetch_shareholders(self, code: str) -> list[dict]:
        """Fetch top 10 shareholders.

        Returns:
            [{name, share_pct, rank}, ...] or empty list
        """
        ...

    @abstractmethod
    def fetch_executives(self, code: str) -> list[dict]:
        """Fetch executives / board members.

        Returns:
            [{name, position}, ...] or empty list
        """
        ...

    @abstractmethod
    def fetch_supply_chain(self, code: str) -> dict:
        """Fetch top 5 suppliers and customers.

        Returns:
            {'suppliers': [{name, ratio}], 'customers': [{name, ratio}]}
        """
        ...

    def close(self):
        """Cleanup if needed (e.g. session close). Override in subclasses."""
        pass
