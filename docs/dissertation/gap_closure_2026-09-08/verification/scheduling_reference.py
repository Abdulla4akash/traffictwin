"""Independent scalar admission reference, 440 predeclared synthetic cases."""
from pathlib import Path
import argparse,copy,hashlib,itertools,json
HERE=Path(__file__).resolve().parent

def smallest(w):return min(range(len(w)),key=lambda r:(w[r],r))
def common(batch,w,q,target):
 n=len(batch['s']);c=batch['C'];s=batch['s'];d=batch['d']
 cand=[batch['a'][i] and batch['radio'][i] and q[target]<c for i in range(n)]
 def scan(mask):
  offsets=[];ranks=[];work=0;count=0
  for i,take in enumerate(mask):
   offsets.append(work);ranks.append(count)
   if take:work+=s[i];count+=1
  return offsets,ranks
 def replace(mask):
  o,h=scan(mask)
  return [cand[i] and w[target]+o[i]<d[i] and q[target]+h[i]<c for i in range(n)]
 masks=[cand]
 for _ in range(3):masks.append(replace(masks[-1]))
 adm=masks[-1];offsets,ranks=scan(adm);fourth=replace(adm)
 gate=[cand[i] and w[target]+offsets[i]>=d[i] for i in range(n)]
 cap=[cand[i] and not adm[i] and not gate[i] for i in range(n)]
 met=[adm[i] and w[target]+offsets[i]+s[i]<=d[i] for i in range(n)]
 # Historical outcome precedence. Retain, rather than repair, the labels.
 outcome=[0 if not batch['a'][i] else 3 if gate[i] else 4 if cap[i] else 7 if not cand[i] else 1 if met[i] else 2 for i in range(n)]
 ww=w.copy();qq=q.copy();ww[target]+=sum(s[i] for i in range(n) if adm[i]);qq[target]+=sum(adm)
 return dict(selected=[target]*n,admitted=adm,coarse=cand,gate=gate,cap=cap,offsets=offsets,ranks=ranks,met=met,outcome=outcome,masks=masks,fourth=fourth,fourth_changes=fourth!=adm,admission_category_disagreements=sum(adm[i]!=(outcome[i] in [1,2]) for i in range(n)),cap_labels_without_capacity_failure=sum(cap[i] and q[target]+ranks[i]<c for i in range(n)),work=ww,load=qq,base_work=w,base_load=q)
def causal(batch,w,q,target=None):
 ww=w.copy();qq=q.copy();selected=[];admitted=[];coarse=[];gates=[];caps=[];offsets=[];met=[];oc=[]
 for i,s in enumerate(batch['s']):
  r=smallest(ww) if target is None else target;selected.append(r)
  candidate=batch['a'][i] and batch['radio'][i] and q[r]<batch['C'];gate=ww[r]<batch['d'][i];cap=qq[r]<batch['C'];take=candidate and gate and cap
  offsets.append(ww[r]-w[r]);coarse.append(candidate);admitted.append(take);gates.append(candidate and not gate);caps.append(candidate and gate and not cap);met.append(take and ww[r]+s<=batch['d'][i])
  oc.append(0 if not batch['a'][i] else 7 if not candidate else 3 if not gate else 4 if not cap else 1 if met[-1] else 2)
  if take:ww[r]+=s;qq[r]+=1
 return dict(selected=selected,admitted=admitted,coarse=coarse,gate=gates,cap=caps,offsets=offsets,met=met,outcome=oc,work=ww,load=qq,base_work=w,base_load=q)
def case(name,w,q,s,d,C=10,K=1,radio=None,a=None):return dict(id=name,w=w,q=q,s=s,d=d,C=C,K=K,radio=radio or [True]*len(s),a=a or [True]*len(s))
def cases():
 hand=[case('hand_four_tasks',[0,0,0],[0,0,0],[40]*4,[100]*4),case('hand_capacity',[20],[1],[10,10],[100,100],2),case('hand_gate_equality',[100],[1],[1],[100]),case('hand_radio_inactive',[0],[0],[10,10,10],[100]*3,radio=[False,True,True],a=[True,False,True]),case('hand_zero_work_tie',[0,0],[0,0],[0,0],[100,100],1),case('hand_nonempty',[60,20],[1,1],[40,40],[100,100]),case('hand_inclusive_success',[0],[0],[100],[100]),case('hand_dependency_chain',[0],[0],[40]*6,[1,1,41,41,81,81])]
 grid=[]
 for R,K,state,si,di,C,ri in itertools.product([1,2,6],[1,5],range(3),range(3),range(2),[1,4],range(2)):
  w=([0]*R if state==0 else [20+20*(r%2) for r in range(R)] if state==1 else [10]+[20]*(R-1));q=([0]*R if state==0 else [1]*R if state==1 else [C]+[1]*(R-1))
  s=[[40]*6,[60,5,40,15,80,10],[0,40,0,80,10,0]][si];d=[[20,100,20,100,20,100],[500]*6][di];radio=[[True]*6,[True,False,True,True,False,True]][ri]
  grid.append(case(f'grid_{R}_{K}_{state}_{si}_{di}_{C}_{ri}',w,q,s,d,C,K,radio))
 return hand+grid

def run(c):
 states={a:(c['w'].copy(),c['q'].copy()) for a in 'ABC'};steps=[]
 for k in range(c['K']):
  target=smallest(states['A'][0]);row={}
  for a in 'ABC':
   w,q=states[a]
   r=common(c,w,q,target) if a=='A' else causal(c,w,q,target if a=='B' else None)
   if a=='C':assert all(causal(c,w,q)==r for _ in range(2))
   row[a]=r;states[a]=(r['work'],r['load'])
  steps.append(row)
 totals={a:dict(admitted=sum(sum(r[a]['admitted']) for r in steps),successes=sum(sum(r[a]['met']) for r in steps),work_pre_drain=states[a][0],work_after_drain=[max(0,w-1000) for w in states[a][0]]) for a in 'ABC'}
 return dict(input=c,steps=steps,totals=totals)
def assert_hands(results):
 expected=[((3,2),(3,2),(4,4)),((1,1),(1,1),(1,1)),((0,0),)*3,((1,1),)*3,((1,1),)*3,((2,2),(2,2),(2,2)),((1,1),)*3,((2,0),(3,0),(3,0))]
 for r,e in zip(results,expected):
  got=tuple((r['totals'][a]['admitted'],r['totals'][a]['successes']) for a in 'ABC');assert got==e,(r['input']['id'],got,e)
 # Nonempty C resolves the tie by index on its second task.
 assert results[5]['steps'][0]['C']['selected']==[1,0]
 assert results[7]['steps'][0]['A']['masks']==[[True]*6,[True,False,False,False,False,False],[True,False,True,True,True,True],[True,False,True,False,False,False]]

def minimise(original):
 c=copy.deepcopy(original);trials=[];changed=True
 while changed and len(trials)<60:
  changed=False
  for i in range(len(c['s'])):
   if len(c['s'])<=1:break
   t=copy.deepcopy(c)
   for key in ['s','d','a','radio']:t[key].pop(i)
   t['K']=1;r=run(t);bad=r['steps'][0]['A']['fourth_changes'];trials.append(dict(input=t,retains_mask_instability=bad))
   if bad:c=t;changed=True;break
 return dict(original_id=original['id'],minimal_by_single_candidate_deletion=not changed,trials=trials,result=run(c))
def main(out):
 inputs=cases();assert len(inputs)==440;results=[run(c) for c in inputs];assert_hands(results[:8])
 bad=[r for r in results if any(s['A']['fourth_changes'] for s in r['steps'])];mini=minimise(bad[0]['input']) if bad else None
 stats={}
 for x,y in [('A','B'),('B','C')]:
  delta=[r['totals'][y]['successes']-r['totals'][x]['successes'] for r in results];ad=[r['totals'][y]['admitted']-r['totals'][x]['admitted'] for r in results]
  stats[x+'_'+y]=dict(success_increase_cases=sum(d>0 for d in delta),success_decrease_cases=sum(d<0 for d in delta),success_unchanged_cases=sum(d==0 for d in delta),admission_increase_cases=sum(d>0 for d in ad),admission_decrease_cases=sum(d<0 for d in ad),admission_unchanged_cases=sum(d==0 for d in ad))
 report=dict(protocol_sha256=hashlib.sha256((HERE/'KERNEL_PROTOCOL.md').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),primary_cases=len(results),minimisation_trials=0 if mini is None else len(mini['trials']),status='reference_hand_checks_passed',fourth_changes_cases=len(bad),fourth_changes_substeps=sum(s['A']['fourth_changes'] for r in results for s in r['steps']),admission_category_disagreements=sum(s['A']['admission_category_disagreements'] for r in results for s in r['steps']),cap_labels_without_capacity_failure=sum(s['A']['cap_labels_without_capacity_failure'] for r in results for s in r['steps']),contrasts=stats,results=results,minimisation=mini)
 assert report['primary_cases']+report['minimisation_trials']<=500
 out.mkdir(parents=True,exist_ok=True);(out/'KERNEL_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['results','minimisation']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);main(p.parse_args().output)
