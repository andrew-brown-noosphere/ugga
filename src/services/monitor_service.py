"""
URL monitoring service for detecting schedule changes.

Monitors UGA schedule PDF URLs for changes and automatically imports
new versions when detected.
"""
import asyncio
import hashlib
import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import httpx

from src.services.course_service import CourseService, create_service

logger = logging.getLogger(__name__)


@dataclass
class MonitoredURL:
    """Configuration for a monitored URL."""
    url: str
    name: str
    last_hash: Optional[str] = None
    last_check: Optional[datetime] = None
    last_change: Optional[datetime] = None
    check_count: int = 0
    error_count: int = 0


@dataclass
class ChangeEvent:
    """Event emitted when a monitored URL changes."""
    url: str
    name: str
    old_hash: Optional[str]
    new_hash: str
    timestamp: datetime


class ScheduleMonitor:
    """
    Monitors UGA schedule PDF URLs for changes.

    Usage:
        monitor = ScheduleMonitor()
        monitor.add_url("https://apps.reg.uga.edu/soc/OnlineSOCspring.pdf", "Spring 2026")

        # Run once
        changes = await monitor.check_all()

        # Or run continuously
        await monitor.run(interval_seconds=3600)  # Check hourly
    """

    # Known UGA schedule URLs
    KNOWN_URLS = {
        "spring": "https://apps.reg.uga.edu/soc/OnlineSOCspring.pdf",
        "summer": "https://apps.reg.uga.edu/soc/OnlineSOCsummer.pdf",
        "fall": "https://apps.reg.uga.edu/soc/OnlineSOCfall.pdf",
    }

    def __init__(
        self,
        service: Optional[CourseService] = None,
        auto_import: bool = True,
    ):
        self.service = service or create_service()
        self.auto_import = auto_import
        self.urls: dict[str, MonitoredURL] = {}
        self.callbacks: list[Callable[[ChangeEvent], None]] = []
        self._running = False

    def add_url(self, url: str, name: str) -> None:
        """Add a URL to monitor."""
        self.urls[url] = MonitoredURL(url=url, name=name)
        logger.info(f"Added URL to monitor: {name} ({url})")

    def add_known_urls(self) -> None:
        """Add all known UGA schedule URLs."""
        for name, url in self.KNOWN_URLS.items():
            self.add_url(url, f"UGA {name.title()} Schedule")

    def on_change(self, callback: Callable[[ChangeEvent], None]) -> None:
        """Register a callback for change events."""
        self.callbacks.append(callback)

    async def check_url(self, url: str) -> Optional[ChangeEvent]:
        """
        Check a single URL for changes.

        Returns a ChangeEvent if the content has changed, None otherwise.
        """
        if url not in self.urls:
            logger.warning(f"URL not registered: {url}")
            return None

        monitored = self.urls[url]
        monitored.check_count += 1
        monitored.last_check = datetime.now()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    timeout=60.0,
                )
                response.raise_for_status()

                # Calculate hash
                content_hash = hashlib.sha256(response.content).hexdigest()

                # Check for change
                if monitored.last_hash and monitored.last_hash != content_hash:
                    event = ChangeEvent(
                        url=url,
                        name=monitored.name,
                        old_hash=monitored.last_hash,
                        new_hash=content_hash,
                        timestamp=datetime.now(),
                    )

                    monitored.last_hash = content_hash
                    monitored.last_change = datetime.now()

                    logger.info(f"Change detected: {monitored.name}")

                    # Auto-import if enabled
                    if self.auto_import:
                        await self._import_pdf(url, response.content)

                    # Notify callbacks
                    for callback in self.callbacks:
                        try:
                            callback(event)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

                    return event

                elif monitored.last_hash is None:
                    # First check - store hash but don't report as change
                    monitored.last_hash = content_hash
                    logger.info(f"Initial hash recorded for {monitored.name}")

                    # Import on first check if auto_import
                    if self.auto_import:
                        await self._import_pdf(url, response.content)

                return None

        except Exception as e:
            monitored.error_count += 1
            logger.error(f"Error checking {monitored.name}: {e}")
            return None

    async def _import_pdf(self, url: str, content: bytes) -> None:
        """Import PDF content into the database."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(content)
                temp_path = f.name

            try:
                schedule, result = self.service.import_pdf(temp_path, url)
                logger.info(
                    f"Imported {schedule.term}: "
                    f"{schedule.total_courses} courses, "
                    f"{schedule.total_sections} sections"
                )
            finally:
                Path(temp_path).unlink()

        except Exception as e:
            logger.error(f"Failed to import PDF: {e}")

    async def check_all(self) -> list[ChangeEvent]:
        """Check all monitored URLs for changes."""
        tasks = [self.check_url(url) for url in self.urls]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def run(
        self,
        interval_seconds: int = 3600,
        max_iterations: Optional[int] = None,
    ) -> None:
        """
        Run the monitor continuously.

        Args:
            interval_seconds: Time between checks (default: 1 hour)
            max_iterations: Maximum number of check cycles (None = infinite)
        """
        self._running = True
        iteration = 0

        logger.info(
            f"Starting schedule monitor. "
            f"Checking {len(self.urls)} URLs every {interval_seconds}s"
        )

        while self._running:
            if max_iterations and iteration >= max_iterations:
                break

            changes = await self.check_all()

            if changes:
                logger.info(f"Detected {len(changes)} change(s)")
            else:
                logger.debug("No changes detected")

            iteration += 1

            if self._running:
                await asyncio.sleep(interval_seconds)

        logger.info("Monitor stopped")

    def stop(self) -> None:
        """Stop the monitor."""
        self._running = False

    def get_status(self) -> dict:
        """Get current monitor status."""
        return {
            "running": self._running,
            "urls": [
                {
                    "url": m.url,
                    "name": m.name,
                    "last_check": m.last_check.isoformat() if m.last_check else None,
                    "last_change": m.last_change.isoformat() if m.last_change else None,
                    "check_count": m.check_count,
                    "error_count": m.error_count,
                }
                for m in self.urls.values()
            ],
        }


async def run_monitor(interval: int = 3600) -> None:
    """Convenience function to run the monitor."""
    monitor = ScheduleMonitor()
    monitor.add_known_urls()

    def on_change(event: ChangeEvent):
        print(f"[{event.timestamp}] Schedule changed: {event.name}")

    monitor.on_change(on_change)
    await monitor.run(interval_seconds=interval)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(run_monitor(interval=60))  # Check every minute for testing
