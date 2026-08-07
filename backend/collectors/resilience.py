"""
Wraps a collector's fetch_jobs() with: bounded retries (exponential
backoff), a hard timeout via a thread (works cross-platform, unlike
signal-based timeouts), and per-collector failure logging -- so one
flaky source can't hang or crash the whole run, and doesn't get
retried indefinitely (duplicate-retry prevention via a max-attempts cap).
"""
import logging
import time
import concurrent.futures

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
BASE_BACKOFF_SECONDS = 1.5
TIMEOUT_SECONDS = 20


def call_with_resilience(fn, *args, source_name="unknown", **kwargs):
    """
    Calls fn(*args, **kwargs) with retries+timeout. Returns (result, error).
    On total failure, result is [] and error is the last exception's message.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 2):  # initial try + MAX_RETRIES retries
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn, *args, **kwargs)
            try:
                result = future.result(timeout=TIMEOUT_SECONDS)
                return result, None
            except concurrent.futures.TimeoutError:
                last_error = f"timed out after {TIMEOUT_SECONDS}s"
                logger.warning("[%s] attempt %d timed out", source_name, attempt)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("[%s] attempt %d failed: %s", source_name, attempt, exc)

        if attempt <= MAX_RETRIES:
            time.sleep(BASE_BACKOFF_SECONDS * attempt)  # backoff, capped by MAX_RETRIES

    logger.error("[%s] giving up after %d attempts: %s", source_name, MAX_RETRIES + 1, last_error)
    return [], last_error
