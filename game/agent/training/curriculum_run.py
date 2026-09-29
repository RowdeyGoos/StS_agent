"""A finite five-stage curriculum; stage changes are explicit new experiments."""
from dataclasses import asdict, dataclass, field
from pathlib import Path
import time

from game.agent.provenance import implementation
from game.agent.action_policy import ALL_LEGAL
from game.agent.runner import prepare_directories
from .benchmark_suite import data
from .checkpoint import load_policy, publish
from .config import TrainingConfig
from .curriculum import SOURCE, training_names
from .ppo_config import PPOConfig, PPOExperiment
from .ppo_run import run_ppo
from .rewards import strict_json


@dataclass(frozen=True, slots=True)
class CurriculumConfig:
    decisions: tuple[int, ...] = (256,256,512,256,256)
    ppo: PPOConfig = field(default_factory=PPOConfig)
    stage_seconds: float = 180.

    def __post_init__(self):
        import math
        if (type(self.decisions) is not tuple or len(self.decisions)!=5 or
                any(type(n) is not int or not 1<=n<=20000 for n in self.decisions) or
                sum(self.decisions)>20000 or type(self.ppo) is not PPOConfig or
                type(self.stage_seconds) not in (int,float) or not math.isfinite(self.stage_seconds) or
                not 0<self.stage_seconds<=720):
            raise ValueError('Choose five bounded stages, at most 20,000 decisions and one hour per learner')

    @classmethod
    def load(cls,path):
        value=strict_json(Path(path).read_text())
        if (type(value) is not dict or set(value)!=set(cls.__dataclass_fields__) or
                type(value['decisions']) is not list or type(value['ppo']) is not dict or
                not set(value['ppo']) <= set(PPOConfig.__dataclass_fields__)):
            raise ValueError('Expected complete curriculum settings')
        return cls(tuple(value['decisions']),PPOConfig(**value['ppo']),value['stage_seconds'])


def run_curriculum(*,checkpoint,config,output_dir,seeds=(17,23,41),cancel=None):
    if (type(seeds) is not tuple or not 3<=len(seeds)<=5 or
            any(type(s) is not int or not 0<=s<2**63 for s in seeds) or len(set(seeds))!=len(seeds)):
        raise ValueError('Choose three to five distinct private learner seeds')
    initial=load_policy(checkpoint, task='combat')
    output=Path(output_dir).resolve()
    output,private=prepare_directories(output,output.with_name(output.name+'-private'))
    path=output/'curriculum.json'
    if path.exists() or (private/'learner-seeds.json').exists():
        raise FileExistsError(output)
    publish(private/'learner-seeds.json',data({'seeds':list(seeds)}),private=True)
    started=time.perf_counter()
    report={'schema':'sts_combat_curriculum_v1','implementation':asdict(implementation()),
        'initial_checkpoint':initial.identity,'config':asdict(config),'replicates':[], 'status':'complete',
        'stage_transition':'Carry inference weights and frozen vocabulary; fresh Adam/action/shuffle RNG per stage; continue private episode cursor.',
        'selection':'Compare all final learners on the same frozen development suite.'}
    report['action_policy'] = initial.model.action_policy
    for number,seed in enumerate(seeds,1):
        row={'name':f'ppo_{number}','stages':[],'status':'running'}
        report['replicates'].append(row)
        current,cursor=checkpoint,0
        for stage,decisions in enumerate(config.decisions):
            experiment=PPOExperiment(training=TrainingConfig(action_policy=initial.model.action_policy),
                ppo=config.ppo,encounters=training_names(stage),source=SOURCE,
                schema='sts_ppo_experiment_v1' if initial.model.action_policy == ALL_LEGAL else 'sts_ppo_experiment_v2')
            stage_dir=output/f'learner-{number}'/f'stage-{stage}'
            result_path,result=run_ppo(checkpoint=current,experiment=experiment,output_dir=stage_dir,
                audit_dir=private/f'learner-{number}'/f'stage-{stage}',decisions=decisions,
                time_limit_seconds=config.stage_seconds,seed=(seed+1009*stage)%2**63,
                start_index=cursor,cancel=cancel)
            row['stages'].append({'stage':stage,'report':str(result_path),'status':result['status'],
                                  'summary':result['summary'],'seconds':result['total_seconds']})
            current=stage_dir/result['last_complete_checkpoint']
            row['last_complete_checkpoint']=str(current)
            if result['status']!='complete':
                row['status']=report['status']=result['status']
                break
            cursor+=sum(len(i['collection'].get('episodes',[])) for i in result['iterations'])
        else:
            row.update(status='complete',checkpoint=str(current),identity=load_policy(current).identity)
        if row['status']!='complete':
            break
    report['total_seconds']=time.perf_counter()-started
    publish(path,data(report))
    return path,report
