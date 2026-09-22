"""Document-only preservation checks. Does not execute research or test code."""
from pathlib import Path
import hashlib, json, re, subprocess, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
old = (HERE / 'first_pass/TrafficTwin_Dissertation.tex').read_text()
new = (ROOT / 'TrafficTwin_Dissertation.tex').read_text()
pattern = r'% BEGIN SOURCE BLOCK (\d+) (\w+)\n(.*?)\n% END SOURCE BLOCK \d+'
def blocks(text):
    return {int(n): (kind, value) for n, kind, value in re.findall(pattern, text, re.S)}
a, b = blocks(old), blocks(new)
changed = [n for n in a if a[n] != b[n]]
expected = {40,47,49,126,175,176,183,185,186,187,188,191,196,201,299}
checks = {}
checks['only_authorized_source_blocks_changed'] = set(changed) == expected
checks['remaining_source_blocks_preserved'] = a.keys() == b.keys()
checks['all_other_tables_exactly_preserved'] = all(a[n] == b[n] for n in a if a[n][0] == 'table' and n not in (186,299))
checks['equations_propositions_proofs_pseudocode_exactly_preserved'] = all(a[n] == b[n] for n in a if a[n][0] in ('equation','proposition','proof','algorithm'))
checks['all_inline_math_exactly_preserved'] = re.findall(r'(?<!\\)\$(.*?)(?<!\\)\$', old, re.S) == re.findall(r'(?<!\\)\$(.*?)(?<!\\)\$', new, re.S)
strip_refs = lambda s: re.sub(r'\\(?:ref|eqref|label)\{[^}]*\}', '', s)
nums = lambda s: re.findall(r'\d+(?:[.,]\d+)*',strip_refs(s))
checks['all_paragraph_numerical_tokens_preserved'] = all(nums(a[n][1]) == nums(b[n][1]) for n in a if a[n][0] == 'paragraph')
checks['bibliography_exactly_preserved'] = old.split(r'\begin{thebibliography}',1)[1].split(r'\end{thebibliography}',1)[0] == new.split(r'\begin{thebibliography}',1)[1].split(r'\end{thebibliography}',1)[0]
checks['task_deadlines_preserved'] = 'deadlines (100, 500, 100) ms' in new
checks['report_age_account_preserved'] = a[100] == b[100] and 'report ages 0, 100, 500 and 1,000 ms' in new
checks['reflection_reselection_correction_preserved'] = a[202] == b[202]
checks['objective_subsection_and_table_removed'] = b[185][1].strip() == b[186][1].strip() == '' and r'\label{tab:9}' not in new
checks['software_testing_neutral_appendix_only'] = new.count('Repository software-testing records are retained separately from the research-campaign validation records.') == 1 and 'software-test failures' not in new and 'retained software test run' not in new and not re.search(r'8,301|8,179|56 failed|66 skipped',new)
checks['clarified_research_decision_attribution'] = 'brainstorming with large language models (LLMs), and subsequent discussion with my PI and permission to proceed' in new and 'discussion of alternatives with AI assistants' not in new
checks['separate_assistance_disclosure_preserved'] = old.split('Codex and ChatGPT assisted',1)[1].split('Protocols were sealed',1)[0] == new.split('Codex and ChatGPT assisted',1)[1].split('Protocols were sealed',1)[0]
checks['remaining_scheduling_wording_clarified'] = 'target timing and reservation visibility' not in new and 'reselecting the destination for each task using workloads updated after earlier admissions' in new
checks['objectives_in_conclusion_with_unevaluated_operator_benefit'] = all(t in b[183][1] for t in ['Against the original objectives','offered/admitted accounting','matched controls','TrafficTwin implements','operator benefit remain unevaluated'])
labels = re.findall(r'\\label\{([^}]+)\}',new)
refs = re.findall(r'\\(?:ref|eqref)\{([^}]+)\}',new)
labels += re.findall(r'\\appendixsections?(?:amepage)?\{([^}]+)\}',new)
# Explicitly include both appendix macros.
labels += re.findall(r'\\appendixsection(?:samepage)?\{([^}]+)\}',new)
checks['internal_reference_targets_defined'] = not (set(refs) - set(labels))
checks['citation_targets_defined'] = set(x for group in re.findall(r'\\cite\{([^}]+)\}',new) for x in group.split(',')) <= set(re.findall(r'\\bibitem\{([^}]+)\}',new))
manifest = json.loads((HERE/'input-manifest.json').read_text())
checks['assets_build_inputs_counting_provenance_unchanged'] = all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest for name,digest in manifest['files_sha256'].items() if name.startswith(('assets/','build_inputs/','revision_checks/counting/')))
source=Path(manifest['source_directory'])
if source.exists():
    current={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.rglob('*')) if p.is_file()}
    checks['entire_original_directory_unchanged'] = current == manifest['files_sha256']
notes=Path(manifest['notes'])
if notes.exists(): checks['original_second_pass_notes_unchanged'] = hashlib.sha256(notes.read_bytes()).hexdigest() == manifest['notes_sha256']
recount = json.loads(subprocess.check_output([sys.executable,str(HERE/'recount.py')],text=True))
checks['word_count_reproducible_and_displayed'] = recount['after']['strict'] == 8355 and 'Automated word count: 8,355' in new
record={'checks':checks,'changed_source_blocks':changed,'unchanged_table_blocks':[n for n in a if a[n][0]=='table' and a[n]==b[n]],'bibliography_entries':len(re.findall(r'\\bibitem\{',new)), 'word_count':recount['after'],'missing_reference_targets':sorted(set(refs)-set(labels))}
print(json.dumps(record,indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
