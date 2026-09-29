"""Freeze a public combat protocol with a bound owner-only seed registry."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import uuid

from game.agent.provenance import implementation
from game.agent.runner import prepare_directories
from .curriculum import SOURCE, STARTS, manifest, start
from .rewards import strict_json
from .scenarios import episode_seed

SCHEMA='sts_combat_benchmark_v1'


def data(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def digest(value):
    return hashlib.sha256(data(value)).hexdigest()


def protocol():
    return {'selection':'development_wins_then_fewer_cutoffs_then_win_hp_fraction_then_name',
            'primary':'selected_PPO_minus_heuristic_heldout_win_rate',
            'criterion':'complete_test_and_group_hoeffding_95_lower_bound_above_zero',
            'uncertainty':'source_group_hoeffding_95','failure_denominator':'all_planned_cases',
            'checkpoint_candidates':'at_least_three_PPO_learner_runs',
            'test_combinations':'transfer_choice_fuzzy,transfer_strength_kin excluded from training and development'}


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    development_cases: int = 64
    test_cases: int = 256
    max_decisions: int = 96
    time_limit_seconds: float = 30.

    def __post_init__(self):
        for name, minimum, maximum in (('development_cases',14,1024),('test_cases',16,4096),('max_decisions',1,512)):
            if type(getattr(self,name)) is not int or not minimum<=getattr(self,name)<=maximum:
                raise ValueError('Invalid benchmark '+name)
        if (type(self.time_limit_seconds) not in (float,int) or not math.isfinite(self.time_limit_seconds)
                or not 0<self.time_limit_seconds<=120):
            raise ValueError('Invalid benchmark time limit')

    @classmethod
    def load(cls,path):
        value=strict_json(Path(path).read_text())
        if type(value) is not dict or set(value)!=set(cls.__dataclass_fields__):
            raise ValueError('Expected complete benchmark settings')
        return cls(**value)


def freeze_suite(output_dir, config=BenchmarkConfig()):
    from .checkpoint import publish
    from gymnasium.utils.seeding import np_random
    output=Path(output_dir).resolve()
    output,private=prepare_directories(output,output.with_name(output.name+'-private'))
    if (output/'suite.json').exists() or (private/'registry.json').exists():
        raise FileExistsError(output)
    cases,registry=[],[]
    # Early campaign combats share a campaign root, group and split. Other
    # authored starts have independent roots. UUIDs hide registry ordinals.
    for split,count in (('validation',config.development_cases),('test',config.test_cases)):
        sources=[s for s in STARTS if split=='test' or not s.test_only]
        groups={}
        for i in range(count):
            item=sources[i%len(sources)]
            repeat=i//len(sources)
            key=('campaign' if item.campaign_combat else item.name,repeat)
            if key not in groups:
                groups[key]=(uuid.uuid4().hex,episode_seed(split,10000+len(groups)))
            group,seed=groups[key]
            case_id=uuid.uuid4().hex
            cases.append({'case_id':case_id,'source_group':group,'split':split,'scenario':item.name})
            policy_seed=int.from_bytes(hashlib.sha256(f'benchmark-random:{seed}:{item.name}'.encode()).digest()[:8],'big')
            # Freeze actual starts before tuning, including held-out starts.
            # Only the trusted evaluator reads these private engine snapshots.
            row={**cases[-1],'reset_seed':seed,'policy_seed':policy_seed,
                 'snapshot_sha256':None,'source_failure':None,'encounter':item.encounter}
            try:
                rng,_=np_random(seed)
                run=item.make(int(rng.integers(0,2**63-1)))
                row['encounter']=run.state.active_encounter_id
                row['snapshot_sha256']=publish(private/(case_id+'.start.json'),data(run.snapshot()),private=True)
            except Exception as error:
                row['source_failure']=type(error).__name__
            registry.append(row)
    private_value={'schema':'sts_benchmark_registry_v1','cases':registry}
    public={'schema':SCHEMA,'source':SOURCE,'implementation':asdict(implementation()),
        'config':asdict(config),'starts':manifest(),'cases':cases,
        'registry_sha256':digest(private_value),
        'protocol':protocol()}
    publish(private/'registry.json',data(private_value),private=True)
    publish(output/'suite.json',data(public))
    return output/'suite.json',public


def load_suite(path):
    path=Path(path).resolve()
    value=strict_json(path.read_text())
    if (type(value) is not dict or set(value)!={'schema','source','implementation','config','starts','cases','registry_sha256','protocol'} or
            value.get('schema')!=SCHEMA or value.get('source')!=SOURCE or value.get('protocol')!=protocol() or
            value.get('implementation')!=asdict(implementation()) or digest(value.get('starts'))!=digest(manifest())):
        raise ValueError('Benchmark suite requires its unchanged source and start definitions')
    if type(value['config']) is not dict or set(value['config'])!=set(BenchmarkConfig.__dataclass_fields__):
        raise ValueError('Invalid benchmark settings')
    config=BenchmarkConfig(**value['config'])
    cases=value['cases']
    if type(cases) is not list or len(cases)!=config.development_cases+config.test_cases:
        raise ValueError('Invalid benchmark population')
    ids,groups=set(),{}
    names={s.name:s for s in STARTS}
    for row in cases:
        if (type(row) is not dict or set(row)!={'case_id','source_group','split','scenario'} or
                any(type(v) is not str for v in row.values()) or row['case_id'] in ids or
                any(len(row[k])!=32 or any(ch not in '0123456789abcdef' for ch in row[k])
                    for k in ('case_id','source_group')) or
                row['scenario'] not in names or row['split'] not in ('validation','test') or
                names[row['scenario']].test_only and row['split']!='test' or
                groups.get(row['source_group'],row['split'])!=row['split']):
            raise ValueError('Invalid cases or cross-split source group')
        ids.add(row['case_id']); groups[row['source_group']]=row['split']
    if any(sum(r['split']==split for r in cases)!=count for split,count in
           (('validation',config.development_cases),('test',config.test_cases))):
        raise ValueError('Population counts disagree')
    private=path.parent.with_name(path.parent.name+'-private')
    return path,value,private


def load_registry(suite, private):
    path=private/'registry.json'
    if private.stat().st_mode & 0o077 or path.stat().st_mode & 0o077:
        raise ValueError('Benchmark seeds require owner-only permissions')
    value=strict_json(path.read_text())
    if digest(value)!=suite['registry_sha256'] or value.get('schema')!='sts_benchmark_registry_v1':
        raise ValueError('Private benchmark registry mismatch')
    rows=value['cases']
    if {r['case_id'] for r in rows}!={r['case_id'] for r in suite['cases']} or len(rows)!=len(suite['cases']):
        raise ValueError('Registry case mapping mismatch')
    result={r['case_id']:r for r in rows}
    roots, groups = {}, {}
    for case in suite['cases']:
        row=result[case['case_id']]
        if (set(row)!={'case_id','source_group','split','scenario','reset_seed','policy_seed','snapshot_sha256','source_failure','encounter'} or
                any(row[k]!=v for k,v in case.items()) or
                any(type(row[k]) is not int or row[k]<0 for k in ('reset_seed','policy_seed')) or
                row['reset_seed']%3!=('train','validation','test').index(case['split'])):
            raise ValueError('Invalid private evaluation seed')
        if ((row['snapshot_sha256'] is None)==(row['source_failure'] is None) or
                row['snapshot_sha256'] is not None and (type(row['snapshot_sha256']) is not str or
                    len(row['snapshot_sha256'])!=64 or any(c not in '0123456789abcdef' for c in row['snapshot_sha256'])) or
                row['source_failure'] is not None and type(row['source_failure']) is not str or
                type(row['encounter']) is not str):
            raise ValueError('Invalid frozen source binding')
        group=case['source_group']
        if (groups.get(group,row['reset_seed'])!=row['reset_seed'] or
                roots.get(row['reset_seed'],group)!=group):
            raise ValueError('Campaign roots must map to exactly one source group')
        groups[group]=row['reset_seed']; roots[row['reset_seed']]=group
    return result


def snapshot_factory(case, registry, private):
    """Every call restores a new engine; an env's secondary seed is irrelevant."""
    from game.headless.run.snapshots import restore_run
    row=registry[case['case_id']]
    if row['source_failure'] is not None:
        raise ValueError('Frozen source construction failed: '+row['source_failure'])
    path=private/(case['case_id']+'.start.json')
    if path.stat().st_mode & 0o077:
        raise ValueError('Engine snapshots require owner-only permissions')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=row['snapshot_sha256']:
        raise ValueError('Frozen combat snapshot mismatch')
    snapshot=strict_json(raw.decode())
    return lambda _:restore_run(snapshot)
