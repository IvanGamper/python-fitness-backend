import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError

from fastapi import HTTPException, Request, Response

import orders_uebung


class OrderServiceTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.database = Path(directory) / "orders.sqlite3"
        self.enterContext(patch.object(orders_uebung, "ORDERS_DB", self.database))

        self.request = Request({"type": "http"})
        self.request.state.request_id = "test-request"
        self.order = orders_uebung.Order(
            order_id="TEST-001",
            sku="PF-SHOULDER-MOBILITY",
            quantity=1,
        )

    def save_test_order(self):
        catalog = BytesIO(b'{"products": [{"sku": "PF-SHOULDER-MOBILITY"}]}')
        with patch.object(orders_uebung, "urlopen", return_value=catalog):
            orders_uebung.create_order(self.order, self.request, Response())

    def test_valid_order_is_saved_and_retrievable(self):
        self.save_test_order()
        self.assertEqual(orders_uebung.get_order(self.order.order_id), self.order)

    def test_product_service_outage_does_not_save_order(self):
        with patch.object(orders_uebung, "urlopen", side_effect=URLError("offline")):
            with self.assertRaises(HTTPException) as error:
                orders_uebung.create_order(self.order, self.request, Response())

        self.assertEqual(error.exception.status_code, 503)
        self.assertFalse(self.database.exists())

    def test_identical_order_can_be_retried_when_product_service_is_offline(self):
        self.save_test_order()
        response = Response()
        with patch.object(orders_uebung, "urlopen", side_effect=URLError("offline")) as product_api:
            saved_order = orders_uebung.create_order(self.order, self.request, response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(saved_order, self.order)
        product_api.assert_not_called()

    def test_same_order_id_with_different_quantity_is_a_conflict(self):
        self.save_test_order()
        changed_order = self.order.model_copy(update={"quantity": 2})
        with self.assertRaises(HTTPException) as error:
            orders_uebung.create_order(changed_order, self.request, Response())

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(orders_uebung.get_order(self.order.order_id), self.order)

    def test_readiness_accepts_a_valid_product_catalog(self):
        with patch.object(orders_uebung, "urlopen", return_value=BytesIO(b'{"products": []}')):
            self.assertEqual(orders_uebung.readiness(), {"status": "ready"})

    def test_liveness_passes_and_readiness_fails_during_product_outage(self):
        with patch.object(orders_uebung, "urlopen", side_effect=URLError("offline")):
            self.assertEqual(orders_uebung.liveness(), {"status": "alive"})
            with self.assertRaises(HTTPException) as error:
                orders_uebung.readiness()

        self.assertEqual(error.exception.status_code, 503)
