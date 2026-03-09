"""Tests for the atomic single-instance lock in src/app.py."""

from __future__ import annotations

import multiprocessing
from pathlib import Path

_SUBPROCESS_TIMEOUT_SECS = 30

# ---------------------------------------------------------------------------
# Subprocess helper (must be importable at the module level for 'spawn')
# ---------------------------------------------------------------------------


def _lock_worker(lock_dir_str: str, result_queue: multiprocessing.Queue) -> None:
    """Try to acquire the single-instance lock and put the result in *result_queue*."""
    # Import inside the worker so it works with the 'spawn' start method.
    from src.app import _try_lock  # noqa: PLC0415

    result = _try_lock(Path(lock_dir_str))
    result_queue.put(result)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSingleInstanceLock:
    """Atomic file-lock tests for _try_lock / _release_lock."""

    def test_acquires_lock_when_free(self, tmp_path):
        """First call acquires the lock."""
        from src.app import _release_lock, _try_lock

        try:
            assert _try_lock(tmp_path) is True
        finally:
            _release_lock(tmp_path)

    def test_lock_file_created(self, tmp_path):
        """A lock file is created on the filesystem."""
        from src.app import _release_lock, _try_lock

        try:
            _try_lock(tmp_path)
            assert (tmp_path / ".lock").exists()
        finally:
            _release_lock(tmp_path)

    def test_lock_file_removed_after_release(self, tmp_path):
        """The lock file is cleaned up after _release_lock."""
        from src.app import _release_lock, _try_lock

        _try_lock(tmp_path)
        _release_lock(tmp_path)
        assert not (tmp_path / ".lock").exists()

    def test_reacquire_after_release(self, tmp_path):
        """After a release the lock can be acquired again."""
        from src.app import _release_lock, _try_lock

        assert _try_lock(tmp_path) is True
        _release_lock(tmp_path)
        assert _try_lock(tmp_path) is True
        _release_lock(tmp_path)

    def test_second_instance_blocked(self, tmp_path):
        """Two concurrent starts: the second one must not acquire the lock.

        The parent process holds the lock; a child process (spawned via
        multiprocessing so it gets a fresh OS-level file-descriptor table)
        must fail to acquire it.
        """
        from src.app import _release_lock, _try_lock

        assert _try_lock(tmp_path) is True
        try:
            ctx = multiprocessing.get_context("spawn")
            q: multiprocessing.Queue = ctx.Queue()
            p = ctx.Process(target=_lock_worker, args=(str(tmp_path), q))
            p.start()
            p.join(timeout=_SUBPROCESS_TIMEOUT_SECS)
            assert p.exitcode == 0, "Worker subprocess did not exit cleanly"
            result = q.get_nowait()
            assert result is False, "Second instance must not acquire the lock"
        finally:
            _release_lock(tmp_path)

    def test_lock_released_when_holder_exits(self, tmp_path):
        """After the holder process exits the lock can be reacquired."""
        from src.app import _release_lock, _try_lock

        ctx = multiprocessing.get_context("spawn")
        q: multiprocessing.Queue = ctx.Queue()
        p = ctx.Process(target=_lock_worker, args=(str(tmp_path), q))
        p.start()
        p.join(timeout=_SUBPROCESS_TIMEOUT_SECS)
        acquired_in_child = q.get_nowait()
        assert acquired_in_child is True, "Child should have acquired the lock"

        # Child exited → OS should have released the lock automatically.
        # On POSIX fcntl.flock is per open-file-description, so closing the fd
        # (process exit) releases it.  On Windows msvcrt.locking is similar.
        # We can now reacquire from the parent.
        try:
            assert _try_lock(tmp_path) is True
        finally:
            _release_lock(tmp_path)
