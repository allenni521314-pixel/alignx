from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from app.core.auth import create_session, validate_session


class AuthSessionTest(unittest.TestCase):
    def test_signed_session_validates_without_memory_state(self):
        token = create_session("user_a", "a@example.com", "seller")

        session = validate_session(token)

        self.assertIsNotNone(session)
        self.assertEqual(session["user_id"], "user_a")
        self.assertEqual(session["email"], "a@example.com")
        self.assertEqual(session["role"], "seller")

    def test_signed_session_rejects_tampered_token(self):
        token = create_session("user_a", "a@example.com", "seller")
        payload, signature = token.split(".", 1)
        tampered = f"{payload[:-1]}A.{signature}"

        self.assertIsNone(validate_session(tampered))

    def test_signed_session_rejects_expired_token(self):
        token = create_session("user_a", "a@example.com", "seller")

        with patch("app.core.auth.time.time", return_value=time.time() + 86400 * 31):
            self.assertIsNone(validate_session(token))


if __name__ == "__main__":
    unittest.main()
