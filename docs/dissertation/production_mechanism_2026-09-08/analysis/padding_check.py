"""Four predeclared padded versions of an existing fixed-target fixture."""
import hashlib,json
import diagnostics as dg
out=dg.HERE/'results'
seed=json.loads((out/'NUMERICAL_FOLLOWUP.json').read_text())['count_compatible']
c=seed['input'];results=[]
for N,R in [(215,9),(2488,10)]:
 for at_end in [False,True]:
  start=N-8 if at_end else 0;ids=list(range(start,start+8))
  s=[0.]*N;d=[100.]*N;e=[False]*N;target=[0]*N;w=[0.]*R;q=[0]*R;w[0]=c['w'][0];q[0]=4
  for j,i in enumerate(ids):s[i]=c['s'][j];e[i]=True
  arr=lambda x,t:dg.jnp.array(x,t)
  ret,trace,ov=dg.production(arr(w,dg.jnp.float32),arr(q,dg.jnp.int32),arr(s,dg.jnp.float32),arr(d,dg.jnp.float32),arr(e,bool),arr(target,dg.jnp.int32),dg.jnp.int32(6220))
  mask=dg.np.asarray(ret[1]);tr=dg.np.asarray(trace);offset=dg.np.asarray(ret[0]);gate=dg.np.asarray(ret[4])
  assert dg.np.array_equal(mask,tr[3]) and dg.np.array_equal(offset,dg.np.asarray(ov[0]))
  assert not mask[~dg.np.asarray(e)].any()
  results.append(dict(N=N,R=R,active_block='end' if at_end else 'start',active_indices=ids,services=c['s'],deadline=100,W0=w[0],Q0=q[0],capacity=6220,production_active_mask=mask[ids].tolist(),active_mirror_masks=tr[:,ids].tolist(),active_final_offsets_ms=offset[ids].tolist(),active_gate_failures=gate[ids].tolist(),capacity_failure_count=float(ret[3]),fourth_changes=not dg.np.array_equal(tr[3],tr[4]),differs_from_exact=mask[ids].tolist()!=seed['exact']['mask']))
report=dict(additional_inputs=4,followup_protocol_sha256=hashlib.sha256((dg.HERE/'FOLLOWUP_PROTOCOL.md').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(open(__file__,'rb').read()).hexdigest(),results=results,scope='Exact equivalence of inactive padding follows from zero contributions. Production arrays use actual N/R dimensions; fixed target0 is imposed. No least-workload-selection, complete-model reachability or observed-frequency claim.')
(out/'PADDING_CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps([dict(N=r['N'],R=r['R'],block=r['active_block'],fourth_changes=r['fourth_changes'],mask=r['production_active_mask'],capacity=r['capacity_failure_count']) for r in results],indent=2))
