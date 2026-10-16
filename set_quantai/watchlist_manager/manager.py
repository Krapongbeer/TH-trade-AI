"""Watchlist & Custom Universe Management Engine (`watchlist_manager`)

Handles:
1. User-custom focus stock lists (Watchlist).
2. Adding, updating, removing stocks with custom notes, priority, target prices, and tags.
3. YAML synchronization with config/watchlist.yaml and database persistence.
"""

from pathlib import Path
from typing import Dict, List, Optional
import yaml
from set_quantai.config import get_project_root
from set_quantai.core.models import WatchlistGroup, WatchlistItem


class WatchlistManager:
    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (get_project_root() / "config" / "watchlist.yaml")
        self.watchlist = self._load_from_yaml()

    def _load_from_yaml(self) -> WatchlistGroup:
        """Load watchlist group from YAML configuration."""
        if not self.config_file.exists():
            return WatchlistGroup(name="รายการหุ้นที่สนใจ (Default Watchlist)")

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                items_data = data.get("items", [])
                items = [WatchlistItem(**item) for item in items_data]
                return WatchlistGroup(
                    name=data.get("name", "รายการหุ้นที่สนใจ"),
                    description=data.get("description", ""),
                    items=items,
                )
        except Exception:
            return WatchlistGroup(name="รายการหุ้นที่สนใจ (Default Watchlist)")

    def save_to_yaml(self) -> None:
        """Persist current watchlist to YAML file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.watchlist.name,
            "description": self.watchlist.description,
            "items": [item.model_dump(mode="json") for item in self.watchlist.items],
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    def add_symbol(
        self,
        symbol: str,
        notes: Optional[str] = None,
        priority: int = 1,
        target_price: Optional[float] = None,
        tags: Optional[List[str]] = None,
        alert_on_signal: bool = True,
    ) -> WatchlistItem:
        """Add or update a stock in the watchlist."""
        symbol = symbol.strip().upper()
        existing = next((i for i in self.watchlist.items if i.symbol == symbol), None)
        if existing:
            if notes is not None:
                existing.notes = notes
            if priority is not None:
                existing.priority = priority
            if target_price is not None:
                existing.target_price = target_price
            if tags is not None:
                existing.tags = tags
            existing.alert_on_signal = alert_on_signal
            item = existing
        else:
            item = WatchlistItem(
                symbol=symbol,
                notes=notes,
                priority=priority,
                target_price=target_price,
                tags=tags or [],
                alert_on_signal=alert_on_signal,
            )
            self.watchlist.items.append(item)

        self.save_to_yaml()
        return item

    def remove_symbol(self, symbol: str) -> bool:
        """Remove a stock from the watchlist."""
        symbol = symbol.strip().upper()
        initial_len = len(self.watchlist.items)
        self.watchlist.items = [i for i in self.watchlist.items if i.symbol != symbol]
        if len(self.watchlist.items) < initial_len:
            self.save_to_yaml()
            return True
        return False

    def get_items(self) -> List[WatchlistItem]:
        """Return all watchlist items sorted by priority ascending."""
        return sorted(self.watchlist.items, key=lambda x: (x.priority, x.symbol))

    def get_symbols(self) -> List[str]:
        """Get list of symbols in watchlist."""
        return [i.symbol for i in self.get_items()]

    def get_item(self, symbol: str) -> Optional[WatchlistItem]:
        symbol = symbol.strip().upper()
        return next((i for i in self.watchlist.items if i.symbol == symbol), None)
