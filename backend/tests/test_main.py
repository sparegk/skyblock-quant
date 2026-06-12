from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app import main


class ApiRouteTests(unittest.TestCase):
    def test_npc_arbitrage_passes_filter_query_params(self) -> None:
        with patch("app.main.get_npc_arbitrage", return_value=[]) as get_npc_arbitrage:
            response = main.npc_arbitrage(
                limit=7,
                min_sell_volume=20_000,
                min_sell_orders=40,
                max_profit_margin=0.2,
                history_snapshots=3,
                min_profitable_snapshots=2,
            )

        self.assertEqual({"items": []}, response)
        get_npc_arbitrage.assert_called_once_with(
            limit=7,
            min_sell_volume=20_000,
            min_sell_orders=40,
            max_profit_margin=0.2,
            history_snapshots=3,
            min_profitable_snapshots=2,
        )

    def test_npc_arbitrage_detail_returns_item(self) -> None:
        expected_item = {"item_id": "TEST_ITEM", "history": []}

        with patch("app.main.get_npc_arbitrage_detail", return_value=expected_item) as detail:
            response = main.npc_arbitrage_detail("test_item", history_snapshots=4)

        self.assertEqual({"item": expected_item}, response)
        detail.assert_called_once_with("test_item", 4)

    def test_npc_arbitrage_detail_raises_404_for_missing_item(self) -> None:
        with patch("app.main.get_npc_arbitrage_detail", return_value=None):
            with self.assertRaises(HTTPException) as error:
                main.npc_arbitrage_detail("missing")

        self.assertEqual(404, error.exception.status_code)


if __name__ == "__main__":
    unittest.main()
