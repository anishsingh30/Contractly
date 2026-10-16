import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import text
from app.config import settings
from app.core.database import engine, AsyncSessionLocal
from app.services.notifications.worker import NotificationWorker

logger = logging.getLogger(__name__)

# Dedicated 64-bit advisory lock key for PostgreSQL distributed coordination
NOTIFICATION_ADVISORY_LOCK_KEY = 84920482


class NotificationScheduler:
    """
    Autonomous background scheduler for Contractly contract milestone & obligation evaluations.

    Concurrency & Multi-Instance Strategy:
    1. In-process: Protected by asyncio.Lock to prevent overlapping evaluations in the same worker.
    2. Multi-instance (PostgreSQL): Protected by a session-level PostgreSQL advisory lock (pg_try_advisory_lock).
       Crucially, the lock is acquired and released on a dedicated single connection (engine.connect())
       to ensure the lock is never acquired on one pooled connection and released on another.
    3. Multi-instance (SQLite Local Dev limitation): SQLite does not provide distributed cross-process
       locks. When running on SQLite, execution relies on the in-process lock and the strict database
       UniqueConstraint on `Notification.deduplication_key` to guarantee duplicate reminders are never inserted.
    4. Resilience: Uncaught evaluation exceptions are caught, logged without leaking secrets or PII,
       and will not crash the API or disable subsequent evaluation cycles.
    """

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._is_running = False
        self._last_run_time: Optional[datetime] = None
        self._last_run_stats: Optional[Dict[str, Any]] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def task(self) -> Optional[asyncio.Task]:
        return self._task

    @property
    def last_run_stats(self) -> Optional[Dict[str, Any]]:
        return self._last_run_stats

    @property
    def last_run_time(self) -> Optional[datetime]:
        return self._last_run_time

    async def execute_cycle(self) -> Dict[str, Any]:
        """
        Executes a single evaluation cycle with distributed coordination if available.
        Safe for manual invocation in tests and background execution in the scheduler loop.
        """
        if self._lock.locked():
            logger.info("[NotificationScheduler] Cycle already in progress in this process; skipping overlapping run.")
            return {"status": "skipped", "reason": "local_lock_busy"}

        async with self._lock:
            is_postgres = not settings.DATABASE_URL.startswith("sqlite")

            if is_postgres:
                # Dedicated connection ensures session-level advisory lock is strictly acquired
                # and released on the exact same physical DB connection, regardless of session commits.
                async with engine.connect() as lock_conn:
                    acquired_dist_lock = False
                    try:
                        res = await lock_conn.execute(
                            text("SELECT pg_try_advisory_lock(:lock_id)"),
                            {"lock_id": NOTIFICATION_ADVISORY_KEY if False else NOTIFICATION_ADVISORY_LOCK_KEY}
                        )
                        acquired_dist_lock = bool(res.scalar())
                        if not acquired_dist_lock:
                            logger.info(
                                "[NotificationScheduler] Another API instance holds the PostgreSQL advisory lock. Skipping this cycle."
                            )
                            return {"status": "skipped", "reason": "postgres_advisory_lock_busy"}
                    except Exception as e:
                        logger.warning(
                            f"[NotificationScheduler] Could not verify PostgreSQL advisory lock ({e}). Continuing under DB deduplication constraints."
                        )

                    try:
                        async with AsyncSessionLocal() as session:
                            stats = await NotificationWorker.evaluate_and_dispatch(session)
                            self._last_run_time = datetime.now(timezone.utc)
                            self._last_run_stats = stats
                            logger.info(
                                "[NotificationScheduler] Successfully completed evaluation cycle. "
                                f"Evaluated contracts: {stats.get('evaluated_contracts', 0)}, "
                                f"Notifications created: {stats.get('notifications_created', 0)}, "
                                f"Skipped duplicates: {stats.get('skipped_dedup', 0)}"
                            )
                            return {"status": "completed", **stats}
                    except Exception as exc:
                        logger.error(f"[NotificationScheduler] Unhandled error during evaluation cycle: {exc}", exc_info=True)
                        return {"status": "error", "error": str(exc)[:200]}
                    finally:
                        if acquired_dist_lock:
                            try:
                                await lock_conn.execute(
                                    text("SELECT pg_advisory_unlock(:lock_id)"),
                                    {"lock_id": NOTIFICATION_ADVISORY_LOCK_KEY}
                                )
                            except Exception as unlock_err:
                                logger.error(f"[NotificationScheduler] Failed to release PostgreSQL advisory lock: {unlock_err}")
            else:
                # SQLite local development fallback
                try:
                    async with AsyncSessionLocal() as session:
                        stats = await NotificationWorker.evaluate_and_dispatch(session)
                        self._last_run_time = datetime.now(timezone.utc)
                        self._last_run_stats = stats
                        logger.info(
                            "[NotificationScheduler] Successfully completed evaluation cycle. "
                            f"Evaluated contracts: {stats.get('evaluated_contracts', 0)}, "
                            f"Notifications created: {stats.get('notifications_created', 0)}, "
                            f"Skipped duplicates: {stats.get('skipped_dedup', 0)}"
                        )
                        return {"status": "completed", **stats}
                except Exception as exc:
                    logger.error(f"[NotificationScheduler] Unhandled error during evaluation cycle: {exc}", exc_info=True)
                    return {"status": "error", "error": str(exc)[:200]}

    async def _loop(self):
        logger.info("[NotificationScheduler] Background evaluation loop started.")
        # Configurable initial delay before first evaluation
        initial_delay = max(0.0, float(settings.NOTIFICATION_SCHEDULER_INITIAL_DELAY_SECONDS))
        if initial_delay > 0:
            try:
                await asyncio.sleep(initial_delay)
            except asyncio.CancelledError:
                logger.info("[NotificationScheduler] Loop cancelled during initial delay.")
                return

        while self._is_running:
            try:
                await self.execute_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[NotificationScheduler] Unexpected loop iteration error: {e}", exc_info=True)

            interval_seconds = max(1.0, float(settings.NOTIFICATION_SCHEDULER_INTERVAL_HOURS) * 3600.0)
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break

        logger.info("[NotificationScheduler] Background loop stopped cleanly.")

    def start(self) -> Optional[asyncio.Task]:
        """Starts the background evaluation task if enabled and not already running."""
        if not settings.NOTIFICATION_SCHEDULER_ENABLED:
            logger.info("[NotificationScheduler] Scheduler is disabled by configuration (NOTIFICATION_SCHEDULER_ENABLED=False).")
            return None

        if self._is_running:
            return self._task

        self._is_running = True
        self._task = asyncio.create_task(self._loop())
        return self._task

    async def stop(self):
        """Cleanly cancels and awaits the background evaluation task."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None


notification_scheduler = NotificationScheduler()
