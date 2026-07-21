import logging
from datetime import datetime

from app.observability import DailyTextFileHandler, PrettyFormatter, request_id_var, session_id_var


def test_daily_log_file_contains_correlation_and_message(tmp_path):
    request_token = request_id_var.set("request-123")
    session_token = session_id_var.set("session-456")
    handler = DailyTextFileHandler(tmp_path)
    handler.setFormatter(PrettyFormatter(False))
    try:
        handler.emit(logging.LogRecord("test", logging.INFO, __file__, 1, "Agent heartbeat", (), None))
        handler.close()
    finally:
        session_id_var.reset(session_token)
        request_id_var.reset(request_token)

    day = datetime.now().astimezone().date().isoformat()
    content = (tmp_path / f"backend-{day}.txt").read_text()
    assert "req=request-123 session=session-456" in content
    assert "Agent heartbeat" in content
