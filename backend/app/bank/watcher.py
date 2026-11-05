"""Watch question_bank/ and auto-import new or changed CSV files."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..db import SessionLocal
from .importer import import_file, is_bank_csv

log = logging.getLogger(__name__)


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: BankWatcher):
        self.watcher = watcher

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory or event.event_type not in ("created", "modified", "moved", "closed"):
            return
        target = getattr(event, "dest_path", "") or event.src_path
        path = Path(str(target))
        if is_bank_csv(path):
            self.watcher.schedule(path)


class BankWatcher:
    """Debounced watchdog observer: spreadsheet apps write files in bursts."""

    def __init__(self, root: Path, debounce_sec: float = 1.5):
        self.root = root
        self.debounce_sec = debounce_sec
        self._timers: dict[Path, threading.Timer] = {}
        self._lock = threading.Lock()
        self._observer = Observer()

    def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(_Handler(self), str(self.root), recursive=True)
        self._observer.daemon = True
        self._observer.start()
        log.info("Watching %s for CSV changes", self.root)

    def stop(self) -> None:
        with self._lock:
            for t in self._timers.values():
                t.cancel()
            self._timers.clear()
        self._observer.stop()
        self._observer.join(timeout=5)

    def schedule(self, path: Path) -> None:
        with self._lock:
            old = self._timers.pop(path, None)
            if old:
                old.cancel()
            t = threading.Timer(self.debounce_sec, self._run, args=(path,))
            t.daemon = True
            self._timers[path] = t
            t.start()

    def _run(self, path: Path) -> None:
        with self._lock:
            self._timers.pop(path, None)
        if not path.exists():
            return
        session = SessionLocal()
        try:
            rep = import_file(session, path, self.root, trigger="watcher")
            if rep:
                log.info("Auto-imported %s (%d new, %d updated, %d skipped)", rep.path, rep.inserted,
                         rep.updated, rep.skipped)
        except Exception:  # pragma: no cover - logged, never crash the watcher thread
            log.exception("Auto-import failed for %s", path)
        finally:
            session.close()
