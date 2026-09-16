"""Package already-complete and independently audited results; no simulations."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parents[2]
OUTPUT = Path('/Users/akashx/Desktop/Dissertation/Experiments 10-12 - 2026-09-16')
REQUIRED_ARTIFACTS = (
    'ANALYSIS.json', 'CELL_RESULTS.csv', 'PAIRED_EFFECTS.csv', 'FINAL_ANALYSIS_AUDIT.json',
    'RESULTS.md', 'FINDINGS.md', 'RESULTS_CHART.png', 'RESULTS_CHART.svg',
    'DENSITY_PLOT.png', 'DENSITY_PLOT.svg', 'DENSITY_POINTS.json',
    'PROTOCOL.md', 'CONFIG.json', 'TRACE_INVENTORY.json', 'OWNER_TASK.md', 'OWNER_AMENDMENT.md',
    'SOURCE_COMPATIBILITY.md', 'SCIENTIFIC_SOURCE_IDENTITY.json',
    'evidence/SOURCE_REVIEW.json', 'evidence/EXECUTION_SEAL.json',
)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def prepare():
    analysis = read(HERE / 'ANALYSIS.json')
    audit = read(HERE / 'FINAL_ANALYSIS_AUDIT.json')
    assert analysis['status'] == 'complete' and analysis['new_full_cells'] == 120
    assert audit['status'] == 'passed' and audit['new_full_cells_checked'] == 120
    for relative in REQUIRED_ARTIFACTS:
        assert (HERE / relative).is_file(), f'Required deliverable missing: {relative}'
    for original, expected in audit['bindings'].items():
        path = Path(original)
        assert path.is_file(), f'Audited file missing: {path}'
        if path.suffix != '.npz':
            assert digest(path) == expected, f'Audited file changed: {path}'
    config = read(HERE / 'CONFIG.json'); raw = Path(config['execution']['raw_root'])
    supervisor = read(raw / 'RUN_SUPERVISOR.json')
    assert supervisor['worker_exit_codes'] == {t: 0 for t in config['traces']}
    assert not list(raw.rglob('FAILED.json'))
    assert not list((HERE / 'evidence').rglob('STOPPED.json'))
    inventory = []
    for source in sorted(raw.rglob('*')):
        if not source.is_file():
            continue
        expected = audit['bindings'].get(str(source))
        if source.suffix == '.npz':
            assert expected, f'Array missing from independent audit: {source}'
            actual = expected
            basis = 'freshly rehashed by independent arithmetic audit after workers completed'
        else:
            actual = digest(source)
            assert expected is None or expected == actual
            basis = 'hashed during packaging'
            dest = HERE / 'runs' / source.relative_to(raw)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                assert digest(dest) == actual, f'Existing compact receipt drift: {dest}'
            else:
                shutil.copy2(source, dest)
        inventory.append({'path': str(source), 'relative_to_raw_root': str(source.relative_to(raw)),
                          'bytes': source.stat().st_size, 'sha256': actual, 'hash_verification': basis,
                          'included_in_compact_packet': source.suffix != '.npz'})
    raw_inventory = {'status': 'complete', 'root': str(raw), 'full_cells': 120,
                     'qualification_attempts': 18, 'blocks': 24,
                     'audit_sha256': digest(HERE / 'FINAL_ANALYSIS_AUDIT.json'),
                     'raw_arrays_remain_local': True,
                     'total_bytes': sum(x['bytes'] for x in inventory), 'files': inventory}
    # Replace only the explicit pre-execution zero-output placeholder.
    old = read(HERE / 'RAW_INVENTORY.json')
    assert old['status'] == 'no_new_raw_outputs'
    (HERE / 'RAW_INVENTORY.json').write_text(json.dumps(raw_inventory, indent=2) + '\n')
    source_paths = {}
    for trace in config['traces']:
        seal = read(HERE / 'evidence' / trace / 'EXECUTION_SEAL.json')
        source_paths.update(seal['sources'])
    for original, expected in source_paths.items():
        path = Path(original); assert digest(path) == expected
        dest = HERE / 'source' / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    # Include the two archived descriptive source tables in the portable packet.
    for point in read(HERE / 'DENSITY_POINTS.json'):
        if point.get('source_path'):
            source = ROOT / point['source_path']
            assert digest(source) == point['source_sha256']
            dest = HERE / 'source' / point['source_path']
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, dest)
    full_receipts = [read(p) for trace in config['traces']
                     for p in (raw / trace / trace).glob('*/attempt_001/VALIDATED.json')]
    write(HERE / 'evidence/FINALIZATION.json', {
        'status': 'complete', 'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_commit': audit['source_commit'], 'full_cells': 120, 'qualification_attempts': 18,
        'blocks': 24, 'contrasts': 15, 'failures': 0, 'retries': 0,
        'full_supervisor_wall_s': supervisor['wall_s'], 'wall_s_per_trace': analysis['wall_s_per_trace'],
        'max_evaluator_peak_rss_bytes': max(x['memory']['evaluator_peak_rss_bytes'] for x in full_receipts),
        'max_runner_high_water_rss_bytes': max(x['memory']['runner_process_high_water_rss_bytes'] for x in full_receipts),
        'concurrency_reduced': (raw / 'REDUCE_CONCURRENCY.json').exists(),
        'raw_total_bytes': raw_inventory['total_bytes'], 'manuscripts_modified': False,
        'analysis_sha256': digest(HERE / 'ANALYSIS.json'),
        'independent_audit_sha256': digest(HERE / 'FINAL_ANALYSIS_AUDIT.json')})
    state = read(HERE / 'WORK_STATUS.json')
    state.update(status='complete', updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 new_full_attempts=120, new_validated_full_cells=120, full_cells_remaining=0,
                 failures=0, retries=0, analysis='complete', independent_arithmetic_audit='passed',
                 current_full_execution_session=None)
    (HERE / 'WORK_STATUS.json').write_text(json.dumps(state, indent=2) + '\n')
    timings = ', '.join(f"{trace}: {seconds/3600:.3f} h" for trace, seconds in analysis['wall_s_per_trace'].items())
    (HERE / 'README.md').write_text(f'''# Three Manchester traces — completed study

All 120 full cells, 24 blocks and 18 qualification attempts passed. There were
zero failures, retries or seed replacements. Trace elapsed times: {timings}.

The design was proposed by Claude and authorised by the owner. The protocol
was sealed before full outcomes. Scientific source:
`{audit['source_commit']}`. This study produced evidence for a paper;
no manuscript was edited.

## Results and verification

- [Results](RESULTS.md) and [findings](FINDINGS.md): all 15 declared contrasts,
  with individual, within-trace and all-15 intervals, including inconclusive results.
- [Cell results](CELL_RESULTS.csv), [paired effects](PAIRED_EFFECTS.csv) and
  [analysis](ANALYSIS.json): machine-readable results.
- [Contrast chart](RESULTS_CHART.png) and [descriptive density plot](DENSITY_PLOT.png).
- [Independent arithmetic audit](FINAL_ANALYSIS_AUDIT.json): all 120 cells,
  18 qualification attempts, 24 blocks and 15 contrasts checked.
- [Finalisation receipt](evidence/FINALIZATION.json), [raw inventory](RAW_INVENTORY.json)
  and [packet manifest](PACKET_MANIFEST.json): timing, memory, provenance and checksums.
- [Compact receipts](runs/): every authorised attempt and block; raw NPZ arrays stay local.

## Fixed design and qualifications

- [Owner task](OWNER_TASK.md), [approved amendment](OWNER_AMENDMENT.md),
  [sealed protocol](PROTOCOL.md) and [configuration](CONFIG.json).
- [Trace inventory](TRACE_INVENTORY.json): all eight candidates, entry-channel
  conventions, remote-main identity and exact morning array differences.
- [Source compatibility](SOURCE_COMPATIBILITY.md),
  [protected source identities](SCIENTIFIC_SOURCE_IDENTITY.json),
  [independent source review](evidence/SOURCE_REVIEW.json) and
  [execution seal](evidence/EXECUTION_SEAL.json).

Qualification matched 14 exogenous inputs across arms and all 59 restart arrays
against the per-task prefix. The primary denominator includes rejected tasks.
PM and event use the documented legacy entry convention. The archived incident
round-robin comparison is unavailable. Density comparisons are descriptive only;
there is no trace pooling, cross-trace testing or equivalence claim.

The [draft PR](https://github.com/Abdulla4akash/traffictwin/pull/144) remains unmerged.
The compact delivery ZIP and external checksums are under
`~/Desktop/Dissertation/Experiments 10-12 - 2026-09-16/`.
''')
    manifest = {str(path.relative_to(HERE)): {'bytes': path.stat().st_size, 'sha256': digest(path)}
                for path in sorted(HERE.rglob('*')) if path.is_file() and '__pycache__' not in path.parts
                and path.name != 'PACKET_MANIFEST.json' and path.suffix != '.pyc'}
    assert not any(name.endswith('.npz') for name in manifest)
    write(HERE / 'PACKET_MANIFEST.json', {'status': 'complete', 'scientific_source_commit': audit['source_commit'],
                                         'full_cells': 120, 'qualification_attempts': 18,
                                         'raw_arrays_included': False, 'files': manifest})
    print(json.dumps({'prepared': True, 'files': len(manifest), 'raw_bytes': raw_inventory['total_bytes']}))


def packet():
    manifest = read(HERE / 'PACKET_MANIFEST.json')
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--', str(HERE)], text=True).strip(), 'Commit completed packet before ZIP'
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / 'TrafficTwin_Experiments_10-12_2026-09-16.zip'
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.comment = f'Results commit {head}; scientific source {manifest["scientific_source_commit"]}'.encode()
        for relative, record in manifest['files'].items():
            source = HERE / relative
            assert digest(source) == record['sha256'] and source.stat().st_size == record['bytes']
            archive.write(source, 'three_traces_2026-09-16/' + relative)
        archive.write(HERE / 'PACKET_MANIFEST.json', 'three_traces_2026-09-16/PACKET_MANIFEST.json')
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        for relative, record in manifest['files'].items():
            assert hashlib.sha256(archive.read('three_traces_2026-09-16/' + relative)).hexdigest() == record['sha256']
    checksum = digest(path)
    write(OUTPUT / 'DELIVERY_CHECKSUMS.json', {
        'status': 'complete', 'results_commit': head, 'scientific_source_commit': manifest['scientific_source_commit'],
        'draft_pr': 'https://github.com/Abdulla4akash/traffictwin/pull/144',
        'packet': {'path': str(path), 'bytes': path.stat().st_size, 'sha256': checksum},
        'manifest_sha256': digest(HERE / 'PACKET_MANIFEST.json'),
        'zip_crc_and_all_member_hashes': 'passed', 'raw_arrays_remain_local': True})
    with (OUTPUT / 'SHA256SUMS').open('x') as stream:
        stream.write(f'{checksum}  {path.name}\n')
        stream.write(f'{digest(OUTPUT / "DELIVERY_CHECKSUMS.json")}  DELIVERY_CHECKSUMS.json\n')
    print(json.dumps({'packet': str(path), 'sha256': checksum, 'results_commit': head}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'zip'])
    action = parser.parse_args().action
    {'prepare': prepare, 'zip': packet}[action]()
