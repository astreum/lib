import errno
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.utils import logging as logging_utils


class TestLoggingResilience(unittest.TestCase):
    def test_file_handler_disables_after_no_space_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            handler = logging_utils.CSVTimedRotatingFileHandler(
                filename=str(Path(tmp_dir) / "node.csv"),
                when="midnight",
                interval=1,
                backupCount=1,
                utc=True,
                encoding="utf-8",
                delay=True,
            )
            handler.setFormatter(logging_utils.CSVFormatter())

            stream = MagicMock()
            stream.flush.side_effect = OSError(errno.ENOSPC, "No space left on device")
            handler.stream = stream

            record = logging.makeLogRecord({"msg": "hello", "levelno": logging.INFO, "levelname": "INFO"})

            handler.emit(record)
            handler.emit(record)

            self.assertTrue(handler._disabled)
            self.assertEqual(stream.write.call_count, 1)
            stream.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
