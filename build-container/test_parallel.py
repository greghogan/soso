"""Event scheduling stays bounded and never swallows build failures."""
import importlib.util
import os
from pathlib import Path
import threading
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('runner', Path(__file__).with_name('run_build.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class ParallelBuildTests(unittest.TestCase):
    def test_worker_limit_and_all_events_finish(self):
        lock = threading.Lock()
        first_pair = threading.Barrier(2, timeout=10)
        active = peak = 0
        finished = []
        def event(number):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            if number in (0, 1):
                first_pair.wait()
            with lock:
                active -= 1
                finished.append(number)
        runner.build_events(range(6), event, 2)
        self.assertEqual(peak, 2)
        self.assertEqual(sorted(finished), list(range(6)))

    def test_failure_propagates_after_workers_finish(self):
        started = threading.Event()
        failing = threading.Event()
        finished = threading.Event()
        def event(number):
            if number == 0:
                self.assertTrue(started.wait(10), 'second worker never started')
                failing.set()
                raise RuntimeError('compiler failed')
            started.set()
            self.assertTrue(failing.wait(10), 'first worker never reached failure')
            finished.set()
        with self.assertRaisesRegex(RuntimeError, 'compiler failed'):
            runner.build_events([0, 1], event, 2)
        self.assertTrue(finished.is_set())

    def test_container_memory_and_cpu_quota_cap_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'meminfo').write_text('MemTotal:       8388608 kB\n')
            (root / 'memory.max').write_text(str(2 * 1024 ** 3))
            (root / 'cpu.max').write_text('max 100000')
            with patch.dict(os.environ, SOSO_BUILD_JOBS='8'), \
                 patch.object(runner.os, 'sched_getaffinity', return_value=set(range(8)), create=True), \
                 patch.object(runner, 'Path', side_effect=lambda path: root / Path(path).name):
                self.assertEqual(runner.build_jobs(8), 2)
                (root / 'cpu.max').write_text('100000 100000')
                self.assertEqual(runner.build_jobs(8), 1)

    def test_invalid_worker_limits_rejected_and_serial_supported(self):
        for value in ('0', '-1', 'auto', '1.5'):
            with patch.dict(os.environ, SOSO_BUILD_JOBS=value):
                with self.assertRaises(ValueError): runner.build_jobs(3)
        with patch.dict(os.environ, SOSO_BUILD_JOBS='1'):
            self.assertEqual(runner.build_jobs(3), 1)
        with patch.dict(os.environ, SOSO_BUILD_JOBS='999'):
            self.assertEqual(runner.build_jobs(1), 1)

if __name__ == '__main__':
    unittest.main()
