"""Offline regressions for the isolated test-DB bootstrap."""
import os
import unittest
from unittest.mock import patch

import scripts.bootstrap_test_db as bootstrap


class BootstrapTestDbTest(unittest.TestCase):
    def test_existing_postgres_url_is_reused_without_starting_anything(self):
        with patch.dict(os.environ, {'OPERATOR_TEST_DATABASE_URL': 'postgresql://u:p@h:5432/db'}), \
                patch.object(bootstrap, 'ensure') as ensure:
            import io, sys
            buf = io.StringIO()
            with patch.object(sys, 'stdout', buf):
                self.assertEqual(bootstrap.main(), 0)
            self.assertIn('postgresql://u:p@h:5432/db', buf.getvalue())
            ensure.assert_not_called()

    def test_non_postgres_url_is_rejected(self):
        with patch.dict(os.environ, {'OPERATOR_TEST_DATABASE_URL': 'sqlite:///x.db'}):
            with self.assertRaises(SystemExit):
                bootstrap.main()


if __name__ == '__main__':
    unittest.main()
