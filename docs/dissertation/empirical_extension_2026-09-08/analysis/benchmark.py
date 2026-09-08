"""Fixed 16-configuration/100-call scheduler benchmark; no traffic simulation."""
from pathlib import Path
import argparse,csv,hashlib,json,os,platform,subprocess,sys,time
os.environ.setdefault('JAX_PLATFORMS','cpu');os.environ.setdefault('JAX_ENABLE_X64','false')
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'experimental'))
import numpy as np
import jax,jaxlib
import jax.numpy as jnp
from kernels import batch_kernel,SOURCE

def fixtures(N,R,busy):
 K=5;i=np.arange(N)[None,:];k=np.arange(K)[:,None];typ=(i+k)%3
 base=np.array([1254/(2.2*1.5*4*.9*5),2100/(2.2*1.5*4*.9*5),15/(2.2*1.5*2*.9)],np.float32)
 work=base[typ]*(.91+((i+7*k)%19)*.01).astype(np.float32)
 args=(np.linspace(40,120,R,dtype=np.float32) if busy else np.zeros(R,np.float32),np.arange(1,R+1,dtype=np.int32) if busy else np.zeros(R,np.int32),np.int32(0),((i+2*k)%5!=0) if busy else ((i+2*k)%10==0),(i+k)%17!=0,np.array([100,500,100],np.float32)[typ],work.astype(np.float32),np.broadcast_to(i%R,(K,N)).astype(np.int32))
 return args

def sync(x):
 for a in jax.tree_util.tree_leaves(x):a.block_until_ready()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 rows=[];raw=[]
 for N,R in [(215,9),(2488,10)]:
  for name,busy in [('sparse',False),('busy',True)]:
   host=fixtures(N,R,busy);args=jax.device_put(host);sync(args)
   h=hashlib.sha256()
   for x in host:h.update(np.ascontiguousarray(x).tobytes())
   for policy in ['ingress_dla','dla','per_task_dla','causal_round_robin']:
    f=batch_kernel(policy);t=time.perf_counter();lower=f.lower(*args);lower_s=time.perf_counter()-t;t=time.perf_counter();compiled=lower.compile();compile_s=time.perf_counter()-t
    for _ in range(5):sync(compiled(*args))
    times=[]
    for rep in range(100):
     t=time.perf_counter_ns();out=compiled(*args);sync(out);elapsed=(time.perf_counter_ns()-t)/1e6;times.append(elapsed);raw.append(dict(N=N,R=R,K=5,fixture=name,policy=policy,rep=rep,milliseconds=elapsed))
    mem=compiled.memory_analysis();md={key:int(getattr(mem,key)) for key in ['argument_size_in_bytes','output_size_in_bytes','temp_size_in_bytes','alias_size_in_bytes']} if mem is not None else None
    text=compiled.as_text(); hlo_hash=hashlib.sha256(text.encode()).hexdigest()
    # Compiler IR retained compactly by checksum; operation counts are descriptive,
    # not a replacement for time measurements or proof of optimisation rules.
    row=dict(N=N,R=R,K=5,fixture=name,policy=policy,input_sha256=h.hexdigest(),lowering_s=lower_s,compilation_s=compile_s,median_ms=float(np.median(times)),q25_ms=float(np.percentile(times,25)),q75_ms=float(np.percentile(times,75)),p95_ms=float(np.percentile(times,95)),min_ms=min(times),max_ms=max(times),memory_analysis_bytes=md,compiled_hlo_sha256=hlo_hash,while_instruction_lines=sum('= (' in line and ' while(' in line for line in text.splitlines()),offered_v2i=int(host[3].sum()),admitted_diagnostic=int(np.asarray(out[1][1]).sum()))
    rows.append(row);print(N,name,policy,round(row['median_ms'],4),flush=True)
    (a.output/'BENCHMARK.partial.json').write_text(json.dumps(rows,indent=2)+'\n')
 info=dict(status='completed',python=sys.version,jax=jax.__version__,jaxlib=jaxlib.__version__,numpy=np.__version__,platform=platform.platform(),machine=platform.machine(),processor=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),devices=[str(x) for x in jax.devices()],x64=jax.config.jax_enable_x64,thread_environment={k:os.environ.get(k,'unset (runtime default)') for k in ['XLA_FLAGS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','JAX_NUM_THREADS']},transfer='device_put before timing; transfer not measured',memory_definition='XLA compiled buffer estimates: argument/output/temporary/alias bytes; not peak RSS or physical device allocation',repetitions=100,warmups=5,full_evaluations=0,protocol_sha256=hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),sources={str(p.relative_to(HERE.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE.parent/'experimental/kernels.py',HERE.parent/'experimental/round_robin.py']},frozen_seq_source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),rows=rows)
 (a.output/'BENCHMARK.json').write_text(json.dumps(info,indent=2)+'\n');(a.output/'BENCHMARK.partial.json').unlink()
 with (a.output/'BENCHMARK_TIMES.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(raw[0]));w.writeheader();w.writerows(raw)
if __name__=='__main__':main()
