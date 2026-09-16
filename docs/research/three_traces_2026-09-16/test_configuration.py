"""Configuration parity and refusal checks; no new evaluator cells."""
import ast
import copy
import fcntl
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyse
import runner as r


class ConfigurationChecks(unittest.TestCase):
    def test_reduced_limit_counts_existing_slot_two(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(r, 'RAW_PARENT', Path(tmp)):
            held = []
            try:
                for index in [1, 2]:
                    stream = (Path(tmp) / f'SLOT_{index}.lock').open('a+')
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    held.append(stream)
                (Path(tmp) / 'REDUCE_CONCURRENCY.json').write_text('{}')
                with patch.object(r.time, 'sleep', side_effect=TimeoutError('correctly waits')):
                    with self.assertRaisesRegex(TimeoutError, 'correctly waits'):
                        r.reserve_slot()
                held.pop(0).close()
                with r.reserve_slot() as granted:
                    self.assertTrue(granted.name.endswith('SLOT_0.lock'))
            finally:
                for stream in held:
                    stream.close()

    def test_scientific_validator_only_declared_parameterisation(self):
        original = (r.LEGACY / 'validation.py').read_text()
        configured = (r.HERE / 'validation.py').read_text()
        configured = configured.replace("T=config['steps'];N=config['trace_dimensions']['N'];R=config['trace_dimensions']['R'];K=5;shape=(T,K,N)", "T=config['steps'];N=215;R=9;K=5;shape=(T,K,N)")
        configured = configured.replace("enter_reset=config['trace_dimensions']['entry_channel_present'],reset_soc_on_enter=False", 'enter_reset=True,reset_soc_on_enter=False')
        configured = configured.replace("need(('enter' in tr.files)==config['trace_dimensions']['entry_channel_present'],'Trace entry-channel configuration mismatch')\n  keep=tr['mask'][:T]&~tr['enter'][:T] if config['trace_dimensions']['entry_channel_present'] else tr['mask'][:T]", "keep=tr['mask'][:T]&~tr['enter'][:T]")
        self.assertEqual(configured, original)

    def test_two_choice_arithmetic_unchanged(self):
        configured = (r.HERE / 'checks.py').read_text()
        configured = configured.replace('    N, R = actions.shape[1], busy.shape[1]\n\n', '')
        configured = configured.replace('(N,), 0, R', '(215,), 0, 9')
        self.assertEqual(configured, (r.LEGACY / 'checks.py').read_text())

    def test_interval_arithmetic_unchanged(self):
        def body(path, name):
            tree = ast.parse(path.read_text())
            return ast.dump(next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name))
        self.assertEqual(body(r.HERE / 'analyse.py', 'interval'), body(r.LEGACY / 'analyse.py', 'interval'))
        values = [0.1, .2, .3, .4, .5, .6, .7, .8]
        widths = [analyse.interval(values, f)['high_pp'] - analyse.interval(values, f)['low_pp'] for f in [1, 5, 15]]
        self.assertLess(widths[0], widths[1]); self.assertLess(widths[1], widths[2])
        with self.assertRaises(ValueError):
            analyse.interval(values[:-1], 15)

    def test_exact_schema_refuses_missing_and_replaced_field(self):
        expected = r.DESIGN['qualification']['expected_array_fields']
        good = {'field_contract': {kind: {field: {} for field in fields} for kind, fields in expected.items()}}
        r.require_schema(good)
        bad = copy.deepcopy(good); bad['field_contract']['step'].pop('lat_sum')
        with self.assertRaisesRegex(ValueError, 'field set'):
            r.require_schema(bad)
        bad['field_contract']['step']['invented_field'] = {}
        with self.assertRaisesRegex(ValueError, 'field set'):
            r.require_schema(bad)

    def test_incomplete_attempt_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'attempt_001'; dest.mkdir()
            with self.assertRaises(FileNotFoundError):
                r.attempt({'output': str(dest)}, {})
            self.assertEqual(list(dest.iterdir()), [])

    def test_receipt_binding_rejects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source'; path.write_text('original')
            bindings = {str(path): r.sha(path)}
            r.check_bindings(bindings); path.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Bound file changed'):
                r.check_bindings(bindings)

    def test_exact_plan_commands_without_execution(self):
        original = (r.TRACE, r.TRACE_HASH, r.RAW)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                seal = Path(tmp) / 'seal'; seal.write_text('{}')
                for trace, tr in r.DESIGN['traces'].items():
                    r.TRACE = Path(tr['path']); r.TRACE_HASH = tr['sha256']; r.RAW = Path(tmp) / trace
                    for b in range(8):
                        for arm in r.ARMS:
                            c = r.config(trace, b, arm, seal)
                            self.assertEqual((c['fleet_seed'], c['evaluator_seed'], c['steps']), (100+b, 200+b, tr['T']))
                            self.assertEqual(c['trace_dimensions'], {k: tr[k] for k in ['N', 'R', 'entry_channel_present']})
                            command = c['command']
                            self.assertNotIn('--ignore-enter', command); self.assertNotIn('--reset-soc-on-enter', command)
                            self.assertEqual(command[command.index('--trace')+1], tr['path'])
                            self.assertEqual(command[command.index('--rsu-cap-abs')+1], '6220')
                            self.assertEqual(command[command.index('--rsu-lb')+1], arm)
                self.assertEqual(len(r.ARMS)*len(r.DESIGN['traces'])*8, 120)
        finally:
            r.TRACE, r.TRACE_HASH, r.RAW = original


if __name__ == '__main__':
    unittest.main()
