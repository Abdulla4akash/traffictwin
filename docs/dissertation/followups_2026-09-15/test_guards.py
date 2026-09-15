"""Refusal tests against synthetic files and preserved short records only."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import shutil
from unittest.mock import patch

import numpy as np

import runner
from analyse import interval
from checks import matched, replay_p2c, validate
from validation import sha

PILOT = Path('/Users/akashx/Downloads/diss_mat/traffictwin-joint-confirmation-raw-2026-09-08/qualification/attempt_02_ingress_dla')


class Guards(unittest.TestCase):
    def test_post_qualification_parent_changes_refused(self):
        qualified = Path('/Users/akashx/scratch/traffictwin-followups-2026-09-15/docs/dissertation/followups_2026-09-15/evidence')
        for name, message in [('BASELINE.json', 'Qualified baseline ledger changed'),
                              ('QUALIFICATION_SEAL.json', 'Qualified qualification seal changed')]:
            with tempfile.TemporaryDirectory() as temp:
                evidence = Path(temp)
                for parent in ['BASELINE.json', 'QUALIFICATION.json', 'QUALIFICATION_SEAL.json']:
                    shutil.copyfile(qualified / parent, evidence / parent)
                value = runner.load(evidence / name)
                if name == 'BASELINE.json':
                    value['records']['0:per_task_dla']['successes'] += 100
                else:
                    value['changed_after_qualification'] = True
                (evidence / name).write_text(json.dumps(value))
                with patch.object(runner, 'EVIDENCE', evidence):
                    with self.assertRaisesRegex(ValueError, message):
                        runner.seal_execution()

    def test_environment_removes_unsealed_modifiers(self):
        with patch.dict(os.environ, {'VEC_JAX_CAP_SCALAR': '1', 'VEC_JAX_RSU_SERVICE_MULT': '.5', 'JAX_ENABLE_X64': 'true', 'XLA_FLAGS': '--bad', 'PYTHONPATH': '/bad'}):
            env = runner.environment(1.)
            self.assertNotIn('VEC_JAX_CAP_SCALAR', env)
            self.assertNotIn('XLA_FLAGS', env)
            self.assertNotIn('PYTHONPATH', env)
            self.assertEqual(env['VEC_JAX_RSU_SERVICE_MULT'], '1.0')
            self.assertEqual(env['JAX_ENABLE_X64'], 'false')

    def test_changed_bound_file_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'source'; p.write_text('original')
            binding = {str(p): sha(p)}; p.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Bound file changed'):
                runner.check_bindings(binding)

    def test_incomplete_attempt_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                runner.attempt({'output': temp, 'frozen_reference': False}, {})
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_changed_exogenous_inputs_refused(self):
        a = {'shared_input_hashes': {'key': 'original'}}
        b = {'shared_input_hashes': {'key': 'changed'}}
        with self.assertRaisesRegex(ValueError, 'exogenous inputs'):
            matched(a, b)

    def test_actor_or_service_metadata_cannot_be_relabelled(self):
        c = runner.load(PILOT / 'VALIDATED.json')['configuration']
        r = validate(PILOT, c)
        self.assertEqual(r['status'], 'passed')
        wrong = copy.deepcopy(c); wrong['service_mult'] = .5
        with self.assertRaisesRegex(ValueError, 'rsu_service_mult'):
            validate(PILOT, wrong)
        wrong = copy.deepcopy(c); wrong['inputs']['actor'] = str(runner.ACTORS['ukfleet'])
        wrong['inputs']['actor_sha256'] = runner.ACTOR_HASHES['ukfleet']
        with self.assertRaisesRegex(ValueError, 'Actor summary'):
            validate(PILOT, wrong)

    def test_altered_count_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            for name in ['per_step.npz', 'per_task.npz']:
                (dest / name).symlink_to(PILOT / name)
            s = runner.load(PILOT / 'summary.json'); s['n_offered'] += 1
            (dest / 'summary.json').write_text(json.dumps(s))
            c = runner.load(PILOT / 'VALIDATED.json')['configuration']
            with self.assertRaisesRegex(ValueError, 'Integer count mismatch'):
                validate(dest, c)

    def test_interval_requires_block_replication(self):
        with self.assertRaises(ValueError):
            interval([1.] * 100, 3)
        x = np.arange(8.)
        a, b = interval(x, 1), interval(x, 10)
        self.assertEqual(a['mean_pp'], 3.5)
        self.assertLess(b['low_pp'], a['low_pp'])
        self.assertGreater(b['high_pp'], a['high_pp'])

    def test_p2c_proposal_and_key_corruption_refused(self):
        original = runner.RAW / 'qualification/05_07_two_choice_dla_p2c/attempt_001'
        if not (original / 'VALIDATED.json').exists():
            self.skipTest('Runs against new short P2C evidence after qualification')
        with np.load(original / 'per_step.npz', allow_pickle=False) as z:
            step = {k: z[k] for k in z.files}
        with np.load(original / 'per_task.npz', allow_pickle=False) as z:
            task = {k: z[k] for k in z.files}
        position = tuple(np.argwhere(task['task_active'] & (step['veh_action'][:, None, :] == 1))[0])
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            np.savez_compressed(p / 'per_step.npz', **step)
            broken = {**task, 'task_selected_execution_rsu': task['task_selected_execution_rsu'].copy()}
            broken['task_selected_execution_rsu'][position] = (broken['task_selected_execution_rsu'][position] + 1) % 9
            np.savez_compressed(p / 'per_task.npz', **broken)
            with self.assertRaisesRegex(ValueError, 'P2C proposal replay'):
                replay_p2c(p)
            np.savez_compressed(p / 'per_task.npz', **task)
            step['exogenous_keys'] = step['exogenous_keys'].copy()
            step['exogenous_keys'][position[0], 1, 0] ^= np.uint32(1)
            np.savez_compressed(p / 'per_step.npz', **step)
            with self.assertRaisesRegex(ValueError, 'P2C proposal replay'):
                replay_p2c(p)


if __name__ == '__main__':
    unittest.main()
