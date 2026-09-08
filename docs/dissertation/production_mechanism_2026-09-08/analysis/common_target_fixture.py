"""One final fixed-target-selection-compatible fixture, with zero entry state."""
import hashlib,json
import diagnostics as dg
out=dg.HERE/'results';old=json.loads((out/'NUMERICAL_FOLLOWUP.json').read_text())['count_compatible']['input']
s=[old['w'][0]/4]*4+old['s'];short=dg.fixture('common_zero_entry_12',s,[100]*12,0,0,types_=[0]*4+old['task_types']);exact=dg.exact(short)
N=215;R=9;work=[0.]*R;count=[0]*R;d=[100.]*N;e=[True]*12+[False]*(N-12);target=[0]*N;services=s+[0.]*(N-12)
arr=lambda x,t:dg.jnp.array(x,t)
ret,trace,_=dg.production(arr(work,dg.jnp.float32),arr(count,dg.jnp.int32),arr(services,dg.jnp.float32),arr(d,dg.jnp.float32),arr(e,bool),arr(target,dg.jnp.int32),dg.jnp.int32(6220))
mask=dg.np.asarray(ret[1]);tr=dg.np.asarray(trace);assert dg.np.array_equal(mask,tr[3]);assert not mask[12:].any()
report=dict(additional_inputs=1,followup_protocol_sha256=hashlib.sha256((dg.HERE/'FOLLOWUP_PROTOCOL.md').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(open(__file__,'rb').read()).hexdigest(),N=N,R=R,entry_work=work,entry_count=count,capacity=6220,active_services=s,active_deadlines=[100]*12,target=0,target_is_entry_argmin=True,exact=exact,production_active_mask=mask[:12].tolist(),active_mirror_masks=tr[:,:12].tolist(),final_offsets_ms=dg.np.asarray(ret[0])[:12].tolist(),gate_failure_mask=dg.np.asarray(ret[4])[:12].tolist(),capacity_failure_count=float(ret[3]),fourth_changes=not dg.np.array_equal(tr[3],tr[4]),scope='Production parameters and actual array dimensions; zero-entry target selection matches the stated common-target rule. Explicit service draws; no actor/RNG/traffic trajectory or observed-frequency claim.')
(out/'COMMON_TARGET_INPUT.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['additional_inputs','production_active_mask','active_mirror_masks','fourth_changes','capacity_failure_count']},indent=2))
