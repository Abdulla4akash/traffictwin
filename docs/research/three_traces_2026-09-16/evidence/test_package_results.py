"""Synthetic regressions for packaging review defects; no study data or evaluator."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import package_results as package


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'checkout'
        self.here = self.root / 'docs/research/study'
        self.raw = Path(self.temp.name) / 'raw'
        self.output = Path(self.temp.name) / 'packet'
        self.here.mkdir(parents=True)
        self.raw.mkdir()
        self.addCleanup(patch.stopall)
        patch.multiple(package, HERE=self.here, ROOT=self.root, OUTPUT=self.output).start()
        for name in [
            'CELL_RESULTS.csv', 'PAIRED_EFFECTS.csv', 'RESULTS.md', 'FINDINGS.md',
            'RESULTS_CHART.png', 'RESULTS_CHART.svg', 'DENSITY_PLOT.png', 'DENSITY_PLOT.svg',
            'PROTOCOL.md', 'TRACE_INVENTORY.json', 'OWNER_TASK.md', 'OWNER_AMENDMENT.md',
            'SOURCE_COMPATIBILITY.md', 'SCIENTIFIC_SOURCE_IDENTITY.json',
            'evidence/SOURCE_REVIEW.json', 'evidence/EXECUTION_SEAL.json',
        ]:
            target = self.here / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('synthetic fixture only\n')
        self.put(self.here / 'ANALYSIS.json', dict(status='complete', new_full_cells=120,
                                                  wall_s_per_trace={'we': 123}))
        self.put(self.here / 'CONFIG.json', dict(execution={'raw_root': str(self.raw)}, traces={'we': {}}))
        self.put(self.here / 'DENSITY_POINTS.json', [])
        self.put(self.here / 'WORK_STATUS.json', {})
        self.put(self.here / 'RAW_INVENTORY.json', {'status': 'no_new_raw_outputs'})
        self.put(self.here / 'evidence/we/EXECUTION_SEAL.json', {'sources': {}})
        self.put(self.raw / 'RUN_SUPERVISOR.json', dict(worker_exit_codes={'we': 0}, wall_s=123))
        self.put(self.raw / 'we/FULL_STARTED.json', {'started_at': '2026-09-16T00:00:00+00:00'})
        self.put(self.raw / 'we/COMPLETE.json', {'finished_at': '2026-09-16T04:00:00+00:00', 'wall_s': 123})
        attempt = self.raw / 'we/we/block_00_ingress_dla/attempt_001'
        self.put(attempt / 'VALIDATED.json', {'memory': {'evaluator_peak_rss_bytes': 100,
                                                       'runner_process_high_water_rss_bytes': 200}})
        self.array = attempt / 'per_step.npz'
        self.array.write_bytes(b'synthetic array placeholder')
        bindings = {str(p): package.digest(p) for p in
                    [self.here / 'ANALYSIS.json', self.here / 'CELL_RESULTS.csv',
                     self.here / 'PAIRED_EFFECTS.csv', self.array]}
        self.put(self.here / 'FINAL_ANALYSIS_AUDIT.json',
                 dict(status='passed', new_full_cells_checked=120, source_commit='synthetic', bindings=bindings))

    @staticmethod
    def put(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            package.prepare()

    def assert_unmodified(self):
        self.assertEqual(package.read(self.here / 'RAW_INVENTORY.json')['status'], 'no_new_raw_outputs')
        self.assertFalse((self.here / 'PACKET_MANIFEST.json').exists())
        self.assertFalse((self.here / 'evidence/FINALIZATION.json').exists())

    def test_changed_audited_csv_stops_before_mutation(self):
        (self.here / 'CELL_RESULTS.csv').write_text('changed after audit\n')
        with self.assertRaisesRegex(AssertionError, 'Audited file changed'):
            self.prepare()
        self.assert_unmodified()

    def test_deleted_audited_array_stops_before_mutation(self):
        self.array.unlink()
        with self.assertRaisesRegex(AssertionError, 'Audited file missing'):
            self.prepare()
        self.assert_unmodified()

    def test_missing_requested_deliverable_stops_before_mutation(self):
        for name in ['PAIRED_EFFECTS.csv', 'RESULTS.md', 'FINDINGS.md',
                     'RESULTS_CHART.png', 'DENSITY_PLOT.png']:
            with self.subTest(name=name):
                path = self.here / name
                saved = path.read_bytes()
                path.unlink()
                try:
                    with self.assertRaisesRegex(AssertionError, 'Required deliverable missing'):
                        self.prepare()
                    self.assert_unmodified()
                finally:
                    path.write_bytes(saved)

    def test_complete_packet_excludes_raw_arrays_and_verifies_members(self):
        self.prepare()
        timing = package.read(self.here / 'evidence/EXECUTION_TIMING.json')['traces']['we']
        self.assertEqual(timing['clock_elapsed_s'], 14400)
        self.assertEqual(timing['runner_monotonic_s'], 123)
        self.assertEqual(timing['clock_minus_monotonic_s'], 14277)
        manifest = package.read(self.here / 'PACKET_MANIFEST.json')
        self.assertFalse(any(name.endswith('.npz') for name in manifest['files']))
        self.assertTrue(self.array.is_file())
        def git(*args):
            subprocess.run(['git', '-C', str(self.root), *args], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        git('init', '-q')
        git('add', '.')
        git('-c', 'user.name=Synthetic Test', '-c', 'user.email=synthetic@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic packaging fixture')
        with contextlib.redirect_stdout(io.StringIO()):
            package.packet()
        receipt = package.read(self.output / 'DELIVERY_CHECKSUMS.json')
        self.assertEqual(receipt['zip_crc_and_all_member_hashes'], 'passed')
        with zipfile.ZipFile(receipt['packet']['path']) as archive:
            self.assertFalse(any(name.endswith('.npz') for name in archive.namelist()))
            self.assertIn('three_traces_2026-09-16/RESULTS.md', archive.namelist())


if __name__ == '__main__':
    unittest.main()
