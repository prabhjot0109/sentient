from __future__ import annotations

import json
import logging
import re
import unittest
from dataclasses import replace
from io import StringIO
from pathlib import Path

from sentient.core.config import load_rag_settings
from sentient.core.logging import bind, configure_logging, current_fields, get_logger

SRC = Path(__file__).resolve().parents[1] / "src" / "sentient"

# A CLI's stdout is its user interface, not a log: `sentient verify` prints a
# report for the person who ran it, and routing that through a logger would send
# it to stderr, drop it below LOG_LEVEL, or wrap it in JSON. The ban is on
# printing from inside the *server*, where stdout is a shared, unstructured sink
# written synchronously from an async handler.
_ALLOWED_TO_PRINT = {"cli.py"}

_PRINT_CALL = re.compile(r"\bprint\(")


class LoggingConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.settings = load_rag_settings()

    def tearDown(self):
        bind(user_key=None, project_id=None, thread_id=None)
        logging.getLogger("sentient").handlers.clear()

    def _capture(self, log_format: str) -> StringIO:
        """Reconfigure for real and redirect the configured handler's stream.

        Building a second handler by hand would test a pipeline the server never
        runs — the context filter lives on the handler `configure_logging` makes.
        """
        configure_logging(replace(self.settings, log_level="INFO", log_format=log_format))
        stream = StringIO()
        logging.getLogger("sentient").handlers[0].setStream(stream)
        return stream

    def test_json_format_emits_one_object_per_record(self):
        stream = self._capture("json")
        bind(user_key="tenant-a", project_id="proj-1")
        get_logger("sentient.test").info("retrieved lore", extra={"chunks": 4})

        payload = json.loads(stream.getvalue().strip())
        self.assertEqual(payload["message"], "retrieved lore")
        self.assertEqual(payload["user_key"], "tenant-a")
        self.assertEqual(payload["project_id"], "proj-1")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["chunks"], 4)

    def test_text_format_appends_the_bound_fields(self):
        stream = self._capture("text")
        bind(user_key="tenant-a")
        get_logger("sentient.test").warning("retrieval failed")

        line = stream.getvalue().strip()
        self.assertIn("WARNING", line)
        self.assertIn("retrieval failed", line)
        self.assertIn("user_key=tenant-a", line)

    def test_an_exception_is_rendered_into_the_json_record(self):
        stream = self._capture("json")
        try:
            raise RuntimeError("embed failed")
        except RuntimeError:
            get_logger("sentient.test").exception("ingest failed")

        payload = json.loads(stream.getvalue().strip())
        self.assertEqual(payload["level"], "ERROR")
        self.assertIn("RuntimeError: embed failed", payload["exception"])

    def test_configuring_twice_does_not_double_every_line(self):
        """lifespan runs per app instance, and the test suite builds many."""
        stream = self._capture("json")
        configure_logging(replace(self.settings, log_level="INFO", log_format="json"))
        logging.getLogger("sentient").handlers[0].setStream(stream)
        get_logger("sentient.test").info("once")

        self.assertEqual(len(stream.getvalue().strip().splitlines()), 1)

    def test_log_level_is_honoured(self):
        configure_logging(replace(self.settings, log_level="WARNING", log_format="json"))
        stream = StringIO()
        logging.getLogger("sentient").handlers[0].setStream(stream)
        get_logger("sentient.test").info("noise")
        get_logger("sentient.test").warning("signal")

        self.assertNotIn("noise", stream.getvalue())
        self.assertIn("signal", stream.getvalue())

    def test_bound_fields_do_not_leak_between_contexts(self):
        bind(user_key="tenant-a")
        self.assertEqual(current_fields()["user_key"], "tenant-a")
        bind(user_key=None)
        self.assertNotIn("user_key", current_fields())

    def test_removing_every_field_leaves_the_bag_empty(self):
        """The ContextVar default is immutable, so there is no shared dict for a
        bind to corrupt on behalf of the next request."""
        bind(user_key="tenant-a")
        bind(user_key=None, project_id=None, thread_id=None)
        self.assertEqual(current_fields(), {})


class LoggingConfigKnobTests(unittest.TestCase):
    def test_defaults_are_info_and_text(self):
        settings = load_rag_settings()
        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.log_format, "text")


class NoPrintInSourceTests(unittest.TestCase):
    """The guard. 59 print() calls is what H5 removes; nothing should add a
    sixtieth. Each one is a synchronous stdout write from an async handler, and
    none of them carries the tenant that would make it a diagnosis."""

    def test_the_server_contains_no_print_calls(self):
        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            if path.name in _ALLOWED_TO_PRINT:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#") or "noqa: T201" in line:
                    continue
                if _PRINT_CALL.search(stripped):
                    offenders.append(f"{path.relative_to(SRC)}:{number}")
        self.assertEqual(offenders, [], "use a logger instead:\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
