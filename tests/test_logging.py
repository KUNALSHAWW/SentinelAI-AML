import json
import logging

from sentinelai.core.logging import ColoredFormatter, JSONFormatter, get_logger, request_id_var, setup_logging


def test_logger_name_not_double_prefixed():
    assert get_logger("sentinelai.api.app").name == "sentinelai.api.app"
    assert get_logger("custom").name == "sentinelai.custom"


def test_extra_fields_and_request_id_reach_json(capsys):
    setup_logging("INFO", "json")
    token = request_id_var.set("req-123")
    try:
        get_logger("t").info("hello", extra={"amount": 42, "case": "X"})
    finally:
        request_id_var.reset(token)
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["message"] == "hello" and line["amount"] == 42 and line["case"] == "X" and line["request_id"] == "req-123"


def test_colored_formatter_does_not_leak_ansi_into_other_handlers():
    record = logging.LogRecord("x", logging.WARNING, __file__, 1, "msg", (), None)
    ColoredFormatter("%(levelname)s %(message)s").format(record)
    assert record.levelname == "WARNING"
    assert "\x1b" not in JSONFormatter().format(record)


def test_setup_is_idempotent():
    setup_logging("INFO", "json")
    n = len(logging.getLogger().handlers)
    setup_logging("INFO", "json")
    assert len(logging.getLogger().handlers) == n
