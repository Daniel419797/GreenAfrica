import unittest
from unittest.mock import patch

from app.events import register_accept, register_reject
from app.models import state, ws_clients


class RvmEventTests(unittest.TestCase):
    def setUp(self):
        state.message = "Ready"
        state.points = 0
        state.last_event = None
        state.last_code = None
        state.last_ai = None
        state.last_rejection_reason = None
        ws_clients.clear()

    def test_accept_increments_points_and_creates_code(self):
        with patch("app.events._broadcast") as broadcast:
            async def noop(_payload):
                return None
            broadcast.side_effect = noop
            register_accept(
                source="ai",
                evidence={"material_label": "pet_clear", "confidence": 0.96},
            )

        self.assertEqual(state.points, 1)
        self.assertEqual(state.message, "PET bottle accepted")
        self.assertIsNotNone(state.last_event)
        self.assertIsNotNone(state.last_code)
        self.assertEqual(len(state.last_code), 8)
        self.assertEqual(state.last_ai["material_label"], "pet_clear")

    def test_reject_does_not_increment_points(self):
        with patch("app.events._broadcast") as broadcast:
            async def noop(_payload):
                return None
            broadcast.side_effect = noop
            register_reject(source="ai", reason="non_pet_material", evidence={"material_label": "glass"})

        self.assertEqual(state.points, 0)
        self.assertEqual(state.message, "Rejected")
        self.assertEqual(state.last_rejection_reason, "non_pet_material")
        self.assertIsNotNone(state.last_event)


if __name__ == "__main__":
    unittest.main()
