"""Full production director, real unpaused native clock, disposable fixture only."""
import argparse,json,os,sys,time,threading,traceback,hashlib,subprocess,math
from pathlib import Path
from combat_lab_outcomes import observed_carriers, clear_window_start, require_native_instance
from combat_lab_finalization import FinalizationGuard
source_dir=Path(__file__).resolve().parent;repo=source_dir.parents[1]
os.environ.update(LAYA_CPU_THREADS='4',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',HF_HUB_OFFLINE='1')
sys.path.insert(0,str(repo));import rimworld_laya as b;import colony_director as d
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--batch',type=Path,default=source_dir/'hard_raids.json')
ap.add_argument('--output',type=Path,required=True,help='A new private result directory; never overwritten')
ap.add_argument('--campaign-id',required=True,help='Exact disposable laboratory campaign UUID')
ap.add_argument('--api-url',default='http://localhost:8765')
ap.add_argument('--native-dll',type=Path,required=True,help='Read-only path to the loaded laboratory DLL for its hash')
ap.add_argument('--native-process-id',type=int,help='Expected owned native process, in addition to the reusable fixture UUID')
ap.add_argument('--native-instance-id',help='Expected native laboratory process instance')
ap.add_argument('--stop-on-failure',action='store_true',help='Retain the first failed case and stop this development batch')
ap.add_argument('--case',help='Select one case from the batch for a fresh-world qualification')
ap.add_argument('--allow-shared-world',action='store_true',help='Development only: allow multiple fixtures; world history and trap knowledge are not reset')
ap.add_argument('--resume-from',type=Path,help='Continue one paused lab case after a strict cutoff, preserving its pawns, injuries and memory')
ap.add_argument('--baseline-setup',type=Path,help='Compare against the exact saved initial lab fixture in a fresh process; never an ordinary save')
ap.add_argument('--declared-carrier-exit-contract',action='store_true',help='Explicit fresh held scripted-exit contract only; no unforced raid credit')
args=ap.parse_args()
cases=json.loads(args.batch.read_text());c=b.RimApiClient(args.api_url,timeout=60)
if args.case:
 cases=[row for row in cases if row['id']==args.case]
 if len(cases)!=1:raise ValueError('The requested case must identify exactly one fixture')
if len(cases)!=1 and not args.allow_shared_world:raise ValueError('Qualification needs one case per fresh world; select --case. Shared worlds require explicit --allow-shared-world for development only.')
if args.declared_carrier_exit_contract and (not args.baseline_setup or args.resume_from or len(cases)!=1 or cases[0]['scenario']!='intercept_perpendicular_exit_contract'):
 raise ValueError('Declared exit mode requires one fresh exact held exit-contract setup; ordinary baseline gate remains strict')
campaign=args.campaign_id
def foreign_details(state):
 details={}
 for pid in set(state.get('unexpected_player_ids',[])+state.get('unexpected_threat_ids',[])):
  try:details[pid]=c.get('/api/v1/pawns/details',id=pid)
  except Exception as exc:details[pid]={'read_error':str(exc)}
 return details
native_info=c.get('/api/v1/combat-lab/info')
assert native_info['test_build'], 'An explicitly opted-in lab build is required'
assert native_info.get('projectile_trace_hooks') is True, 'Read-only projectile/death evidence hooks are unavailable'
assert native_info.get('native_down_transition_hook') is True, 'Native down-transition evidence is unavailable'
native_process_id=native_info['native_process_id'];native_instance_id=native_info['native_instance_id']
assert isinstance(native_process_id,int) and native_process_id>0 and native_instance_id
assert args.native_process_id is None or args.native_process_id==native_process_id, 'Different native process; no test started'
assert args.native_instance_id is None or args.native_instance_id==native_instance_id, 'Different native instance; no test started'
def require_instance(state):
 return require_native_instance(state,native_process_id,native_instance_id)
def scoped_pause():
 require_instance(c.get('/api/v1/combat-lab/state',campaign_id=campaign,include_trace=False))
 # Pause is explicit; zero ticks alone does not change the native time speed.
 reply=require_instance(c.post('/api/v1/combat-lab/step',body={'campaign_id':campaign,'ticks':0,'pause':True,
     'expected_native_instance_id':native_instance_id,'include_trace':False}))
 for _ in range(40):
  if c.get('/api/v1/game/state')['is_paused']:return reply
  time.sleep(.05)
 raise RuntimeError('Owned laboratory pause readback timed out')
if native_info.get('prior_fixture_on_current_map') and not args.allow_shared_world and not args.resume_from and not args.baseline_setup:
 raise ValueError('A prior fixture already used this map; a fresh native world is required for qualification')
assert c.get('/api/v1/colony/ending-evidence')['campaign_id']==campaign, 'Campaign changed; no test setup sent'
lab=args.output.resolve();lab.mkdir(parents=True,exist_ok=False)
(lab/'cases').mkdir()
runtime_sources={Path(m.__file__).name:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (b,d,b.combat_planner)}
for diagnostic_file in (Path(__file__).with_name('CombatLabController.cs'),Path(__file__).with_name('CombatLabProjectileTrace.cs'),Path(__file__).with_name('combat_lab_outcomes.py'),Path(__file__).with_name('combat_lab_finalization.py')):
 runtime_sources[diagnostic_file.name]=hashlib.sha256(diagnostic_file.read_bytes()).hexdigest()
native_file=args.native_dll
native_sha=hashlib.sha256(native_file.read_bytes()).hexdigest()
harness_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
fixture_sha=hashlib.sha256((source_dir/'CombatLabController.cs').read_bytes()).hexdigest()
for case in cases:
 folder=lab/'cases'/case['id'];folder.mkdir(exist_ok=False)
 request={k:v for k,v in case.items() if k in ('scenario','seed','attackers','defenders','cover','micro','enemy_xenotype','fortified','defense_layout')};request['campaign_id']=campaign
 if args.baseline_setup:
  if args.resume_from or (not native_info.get('loaded_initial_baseline') and not args.declared_carrier_exit_contract):
   raise ValueError('The exact initial laboratory baseline was not loaded; no fixture setup sent')
  prior=json.loads(args.baseline_setup.read_text())
  initial=require_instance(c.get('/api/v1/combat-lab/state',campaign_id=campaign))
  if args.declared_carrier_exit_contract:
   if native_info.get('loaded_initial_baseline') or not initial['holding_initial_clock'] or len(initial['allies'])!=1 or len(initial['enemies'])!=1:
    raise ValueError('Fresh held declared exit contract is not present; no setup/recovery permitted')
   enemy=initial['enemies'][0]
   if enemy.get('native_kidnapper') is not True or enemy.get('job_exit_map_on_arrival') is not True or enemy.get('carried_id')!=initial['captive']['id']:
    raise ValueError('Actual native abduction/exit binding is missing')
  if initial['scenario']!=case['scenario'] or initial['tick']!=prior['tick'] or initial['stepped_ticks']!=0:
   raise ValueError('Initial lab scenario/tick changed; do not regenerate a failed cohort')
  def same(a,b):
   if isinstance(a,(float,int)) and not isinstance(a,bool):
    return isinstance(b,(float,int)) and math.isclose(a,b,rel_tol=1e-5,abs_tol=1e-6)
   return a==b
  fields=('id','name','dead','downed','spawned','health','bleeding','drafted','x','z','food','rest','mood',
          'weapon','shooting','xenotype','traits','genes','body_size','aim_delay','disabled_work','speed','move_ticks','doctor_enabled')
  for key in ('allies','enemies','captive'):
   before=prior[key] if key!='captive' else [prior[key]] if prior.get(key) else []
   after=initial[key] if key!='captive' else [initial[key]] if initial.get(key) else []
   if len(before)!=len(after) or any(not same(a.get(f),b.get(f)) for a,b in zip(before,after) for f in fields):
    raise ValueError(f'Saved initial {key} cohort changed; no battle started')
  if initial['initial_random_state']!=prior['initial_random_state']:
   raise ValueError('Saved initial RNG state changed; no battle started')
  (folder/'baseline-comparison.json').write_text(json.dumps(dict(source=str(args.baseline_setup.resolve()),
   source_sha256=hashlib.sha256(args.baseline_setup.read_bytes()).hexdigest(),same_native_cohort=True,same_declared_start_rng=True,
   statement=('Fresh explicitly declared scripted exit setup, same native cohort/RNG, not an unforced raid qualification' if args.declared_carrier_exit_contract else 'Exact pre-fight native fixture restored in a fresh process. No cohort reroll or ordinary colony load.'))))
 elif args.resume_from:
  if len(cases)!=1:raise ValueError('Resuming requires exactly one case')
  prior=json.loads((args.resume_from/'setup.json').read_text())
  initial=require_instance(c.get('/api/v1/combat-lab/state',campaign_id=campaign))
  if initial['start_tick']!=prior['start_tick'] or [p['id'] for p in initial['allies']]!=[p['id'] for p in prior['allies']]:
   raise ValueError('Native fixture changed; no resume or setup sent')
  (folder/'colony-state.json').write_bytes((args.resume_from/'colony-state.json').read_bytes())
  (folder/'resume-proof.json').write_text(json.dumps(dict(source=str(args.resume_from.resolve()),
   memory_sha256=hashlib.sha256((folder/'colony-state.json').read_bytes()).hexdigest(),
   statement='Same current native fixture; no setup, pawn/health/needs reset, save or load was sent.')))
 else:initial=b.RimApiClient(args.api_url,timeout=180).post('/api/v1/combat-lab/setup',body=request)
 (folder/'setup.json').write_text(json.dumps(initial,indent=2));(folder/'request.json').write_text(json.dumps(request,indent=2))
 if initial.get('unexpected_player_ids') or initial.get('unexpected_threat_ids'):
  (folder/'foreign-actors.json').write_text(json.dumps(foreign_details(initial),indent=2))
  raise ValueError('Unexpected actor survived fixture setup; no director or observer started')
 trace=[];seen_down=set();stop=threading.Event();outcome={};started=time.monotonic();accelerated_stage_ticks=0
 closing_guard=FinalizationGuard({p['id'] for p in initial['allies']},(initial.get('captive') or {}).get('id'))
 restore_director_writes=closing_guard.install(b.RimApiClient)
 obsout=(folder/'observer-console.log').open('w')
 observer=subprocess.Popen([sys.executable,str(repo.parent/'scoped_observer_20261021.py'),'--runtime-root',str(repo),
  '--expected-native-process-id',str(native_process_id),'--expected-native-instance-id',native_instance_id,
  '--expected-campaign-id',campaign,'--parent-pid',str(os.getpid()),'--api-url',args.api_url,'--pid-file',str(folder/'observer.pid'),
  '--status',str(folder/'observer-status.json'),'--log',str(folder/'observer.jsonl')],stdout=obsout,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 def monitor():
  global accelerated_stage_ticks
  try:
   clear_since=None;last_print=0;completed=False;care_expired=False;initial_released=False
   while not stop.wait(1):
    s=require_instance(c.get('/api/v1/combat-lab/state',campaign_id=campaign,include_trace=False))
    if not initial_released:
     try:ready=json.loads((folder/'runtime-status.json').read_text()).get('state')=='running'
     except (OSError,ValueError):ready=False
     if ready:
      release=c.post('/api/v1/combat-lab/begin',body={'campaign_id':campaign,'expected_native_instance_id':native_instance_id,'micro':case.get('micro',True)})
      (folder/'initial-clock-release.json').write_text(json.dumps(release,indent=2))
      if release.get('initial_rng_applied')!=initial['initial_random_state']:
       raise ValueError('Recorded initial RNG was not applied at the start of this laboratory battle')
      initial_released=True
    seen_down.update(p['id'] for p in s['allies'] if p['downed'] or p['dead'])
    seen_down.update(s['ever_downed_ids'])
    active=[p for p in s['enemies'] if p['spawned'] and not p['dead'] and not p['downed']]
    carried=observed_carriers(s)
    gone=[p['id'] for p in s['allies'] if p['dead'] or not p['spawned'] and p['id'] not in carried]
    captive=s.get('captive')
    captive_gone=bool(captive and (captive['dead'] or not captive['spawned'] and captive['id'] not in carried))
    if gone or captive_gone:
     outcome.update(state=s,reason='lost_defender' if gone else 'lost_captive');break
    staging=bool(active) and all('Stage' in str(p.get('lord_toil')) for p in active)
    if s.get('unexpected_player_ids') or s.get('unexpected_threat_ids'):
     outcome.update(state=s,reason='fixture_contamination',foreign_actor_details=foreign_details(s));break
    trace.append({'at':b.utc_now(),'tick':s['tick'],'active':len(active),'staging':staging,'shots':sum(p['shots'] for p in s['allies']),
       'control':s.get('control'),'allies':[{k:p.get(k) for k in ('id','health','downed','dead','spawned','job','drafted','x','z')} for p in s['allies']]})
    if time.monotonic()-last_print>=10:
     print(json.dumps({'case':case['id'],'tick':s['tick'],'native_ticks':s['stepped_ticks'],'active':len(active),'shots':trace[-1]['shots'],'allies_up':sum(p['spawned'] and not p['dead'] and not p['downed'] for p in s['allies'])}),flush=True);last_print=time.monotonic()
    clear_since=clear_window_start(bool(active),clear_since,time.monotonic())
    if not active:
     captive=s.get('captive')
     care_ok=not case.get('require_captive_tended') or bool(captive and captive['spawned'] and not captive['dead'] and captive['bleeding']<=0
        and (not captive['downed'] or captive.get('in_bed')))
     if case.get('require_defenders_stabilized'):
      care_ok=care_ok and all(p['spawned'] and not p['dead'] and p['bleeding']<=0 and (not p['downed'] or p.get('in_bed')) for p in s['allies'])
     completed=closing_guard.observe(s,case)
     if completed:
      fresh=closing_guard.try_close(lambda:require_instance(c.get('/api/v1/combat-lab/state',campaign_id=campaign,include_trace=False)),case)
      completed=fresh is not None
      if completed:s=fresh
     care_expired=time.monotonic()-clear_since>case.get('post_clear_seconds',180)
     done=completed or care_expired
    else:
     completed=False;closing_guard.observe(s,case);done=False
    defeated=bool(seen_down) if case.get('fail_fast',True) else all(p['dead'] or p['downed'] or not p['spawned'] for p in s['allies'])
    if done or defeated or time.monotonic()-started>case.get('timeout_seconds',220):
     outcome.update(state=s,reason='clear' if completed else 'postcombat_incomplete' if care_expired else
       'strict_down_cutoff' if defeated and case.get('fail_fast',True) else 'defeated' if defeated else 'timeout');break
    if staging and case.get('accelerate_staging_ticks'):
     status_path=folder/'runtime-status.json'
     try:ready=json.loads(status_path.read_text()).get('state')=='running'
     except (OSError,ValueError):ready=False
     # Explicit laboratory clock acceleration only while the native Lord is
     # staging; the final approach and assault run on the ordinary live clock.
     remaining=case.get('accelerate_staging_until',178000)-s['stepped_ticks']
     if ready and remaining>0:
      n=min(1200,case['accelerate_staging_ticks'],remaining)
      c.post('/api/v1/combat-lab/step',body={'campaign_id':campaign,'ticks':n,'include_trace':False})
      accelerated_stage_ticks+=n
  except Exception:
   outcome.update(reason='monitor_error',error=traceback.format_exc())
  finally:
   closing_guard.request_director_stop()
   try:scoped_pause()
   except Exception as exc:outcome['pause_error']=str(exc)
 worker=threading.Thread(target=monitor,daemon=True);worker.start()
 original=sys.argv;sys.argv=['colony_director.py','--api-url',args.api_url,'--interval','10','--state',str(folder/'colony-state.json'),
   '--log',str(folder/'director-decisions.jsonl'),'--pid-file',str(folder/'director.pid'),'--runtime-status',str(folder/'runtime-status.json')]
 try:outcome['director_exit']=d.main()
 except KeyboardInterrupt:
  outcome['director_exit']='outer_interrupt'
  outcome.setdefault('reason','interrupted')
 except Exception:outcome.update(director_error=traceback.format_exc())
 finally:
  restore_director_writes()
  sys.argv=original;stop.set();worker.join(timeout=5)
  if worker.is_alive():raise RuntimeError('Terminal monitor did not finish; preserve partial instead of an unverified result')
 if observer.poll() is None:observer.terminate()
 observer.wait(timeout=15);obsout.close()
 # Stop the only other speed writer before the final pause. A pending observer
 # request could otherwise unpause after the monitor/director had both stopped.
 scoped_pause()
 if not c.get('/api/v1/game/state')['is_paused']:
  raise RuntimeError('Disposable test did not pause after observer exit')
 (folder/'observer-stop-proof.json').write_text(json.dumps({'pid':observer.pid,'exit':observer.returncode,'reason':'Expected disposable test completion; game paused after director stopped'}))
 state=require_instance(c.get('/api/v1/combat-lab/state',campaign_id=campaign))
 seen_down.update(p['id'] for sample in state['samples'] for p in sample['allies'] if p['downed'] or p['dead'])
 seen_down.update(state['ever_downed_ids'])
 active=[p['id'] for p in state['enemies'] if p['spawned'] and not p['dead'] and not p['downed']]
 lost=[p['id'] for p in state['allies'] if p['dead'] or not p['spawned']]
 drafted=[p['id'] for p in state['allies'] if p['drafted']]
 captive=state.get('captive');safe_captive=not captive or captive['spawned'] and not captive['dead']
 care_ok=not case.get('require_captive_tended') or bool(captive and captive['spawned'] and not captive['dead'] and captive['bleeding']<=0
    and (not captive['downed'] or captive.get('in_bed')))
 if case.get('require_defenders_stabilized'):
  care_ok=care_ok and all(p['spawned'] and not p['dead'] and p['bleeding']<=0 and (not p['downed'] or p.get('in_bed')) for p in state['allies'])
 if outcome.get('reason')=='clear' and lost:
  outcome['reason']='clear_with_missing_defenders'
 if outcome.get('reason')=='clear' and not safe_captive:
  outcome['reason']='clear_without_safe_captive'
 complete=outcome.get('reason')=='clear' and not outcome.get('director_error')
 phase_checks={}
 if case.get('accelerate_staging_ticks'):
  staged=[sample for sample in state['samples'] if sample['enemies'] and all('Stage' in str(p.get('toil')) for p in sample['enemies'])]
  jobs={p.get('job') for sample in staged for p in sample['allies']}
  individual=[]
  for pawn in state['allies']:
   observations=[p for sample in staged for p in sample['allies'] if p['id']==pawn['id']]
   individual.append({'pawn_id':pawn['id'],'ate':any(p.get('job')=='Ingest' for p in observations),
    'slept':any(p.get('job')=='LayDown' for p in observations),
    'minimum_food':min((p['food'] for p in observations),default=None),
    'minimum_rest':min((p['rest'] for p in observations),default=None)})
  phase_checks={'three_game_days_observed':state['stepped_ticks']>=180000,
    'no_staging_draft':bool(staged) and not any(p['drafted'] for sample in staged for p in sample['allies']),
    'actual_meal_and_sleep_observed':{'Ingest','LayDown'}<=jobs,
    'each_pawn_ate_and_slept':bool(individual) and all(p['ate'] and p['slept'] for p in individual),
    'individual_staging_needs':individual,
    'assault_transition_observed':any(not row['staging'] and row['active'] for row in trace),
    'sampled_staging_jobs':sorted(str(j) for j in jobs)}
  complete=complete and all(v for v in phase_checks.values() if isinstance(v,bool))
 passed=complete and not active and not seen_down and not lost and not drafted and safe_captive and care_ok
 outcome.update(case=case,request=request,state=state,trace=trace,ever_downed_ids=sorted(seen_down),lost_ids=lost,active_enemy_ids=active,
   drafted_ids=drafted,observed_carriers=observed_carriers(state),pass_no_down_no_loss_defense=passed,seconds=time.monotonic()-started,
   pass_no_death_kidnap_stabilized_defense=complete and not active and not lost and not drafted and safe_captive and care_ok,
   runtime_sources=runtime_sources,native_dll_sha256=native_sha,campaign_id=campaign,
   harness_sha256=harness_sha,fixture_source_sha256=fixture_sha,accelerated_stage_ticks=accelerated_stage_ticks,
   native_process_id=native_process_id,native_instance_id=native_instance_id,
   phase_checks=phase_checks,closure_barrier=closing_guard.evidence(),test_protocol='real_time_director_scripted_exit_contract' if args.declared_carrier_exit_contract else 'real_time_director',
   is_unforced_raid_qualification=not args.declared_carrier_exit_contract,
   isolation=('Fresh declared native initial scripted-exit contract, no unforced raid credit' if args.declared_carrier_exit_contract else
     'exact saved initial native laboratory fixture in a fresh process' if args.baseline_setup else
     'shared native world; development only' if args.allow_shared_world else 'single fixture in a fresh native world'),
   test_clock=('Actual native engine with explicit lab tick steps during confirmed staging; final approach/assault use the live clock. '
      if case.get('accelerate_staging_ticks') else 'Actual unpaused engine. ')
      +'Full director.main and production stream_observer process. Requests and decisions are unchanged before closure; a declared post-outcome write barrier blocks later main-thread requests without inventing success or undoing an order. Monitor pauses after outcome; no ordinary colony loaded.')
 (folder/'result.json').write_text(json.dumps(outcome,indent=2));print(json.dumps({k:outcome[k] for k in ('case','pass_no_down_no_loss_defense','reason','ever_downed_ids','lost_ids','active_enemy_ids','drafted_ids','seconds')}),flush=True)
 if args.stop_on_failure and not passed:break
