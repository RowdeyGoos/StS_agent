"""Typed public features and hierarchical pooling over the existing study facts.

The original semantic projection remains the single public-information boundary.
Its dense rows exist temporarily for validation/audits, never as compact network
inputs or retained rollout arrays. No mechanics are fitted from DEV or TEST.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import numpy as np
import torch
from torch import nn

from game.agent.contracts import full as f
from .projection import StudyEncoder, StudyFeatures
from .spec import channels, ROLES, PILES, EFFECT_SLOTS, FeatureSpec

SCHEMA = 'sts_typed_combat_entities_v1'
GROUPS = ('player', 'selection', 'enemy', 'potion', 'relic', 'card:none') + tuple('card:'+p for p in PILES)
EFFECT_WIDTH = 32
COMMON = ('hp','max_hp','block','alive','infinite_hp','slot','selection_source')
BOOLS = {'alive','infinite_hp','eligible','manual_confirmation','selection_source',
         'uses_target','all_enemies','mechanics.description_complete','history.complete',
         'threat.displayed_lethal','item.show_counter','item.melted',
         'present','complete','phase_observed'}


def _allowed(name, role):
    if name.startswith('pile='):
        return role == 'card'
    stem = name.rsplit('.',1)[0] if name.endswith(('.known','.scaled','.log')) else name.split('=')[0]
    if stem in COMMON:
        return True
    if role == 'player':
        return stem in ('energy','stars') or stem.startswith(('count.','actions.','power.','turn.','threat.'))
    if role == 'enemy':
        return stem == 'intent' or stem.startswith(('intent.','power.','history.'))
    if role == 'card':
        return stem in ('energy','stars','position','selected','eligible','card_type',
                        'damage','card_block','draw','uses_target','all_enemies','hits',
                        'mechanics.description_complete') or stem.startswith('card.')
    if role in ('potion','relic'):
        return stem == 'mechanics.description_complete' or stem.startswith('item.')
    if role == 'selection':
        return stem in ('minimum','maximum','selected','manual_confirmation') or stem.startswith('selection.')
    raise ValueError('Unknown compact entity role')


def _fields(names):
    """Known + one magnitude, retaining one-hot mechanical categories.

Use the existing signed log for numbers and a raw bit for Boolean fields.
Known flags stay separate: unknown does not become known zero.
"""
    result=[]
    for name in names:
        if name.endswith('.scaled'):
            continue
        if name.endswith('.log'):
            base=name[:-4]
            if base in BOOLS or base.split('.')[-1] in BOOLS:
                result.append((base+'.scaled',100.))
                continue
        result.append((name,1.))
    return tuple(result)


@lru_cache(maxsize=3)
def layout(richness):
    names=tuple(n for _,n in channels(richness))
    role_fields={role:_fields(n for n in names if _allowed(n,role)) for role in ROLES}
    effect_names=tuple(n.removeprefix('mechanics.effect.0.') for n in names
                       if n.startswith('mechanics.effect.0.'))
    return role_fields, _fields(effect_names)


def layout_binding(richness):
    fields,effects=layout(richness)
    return dict(schema=SCHEMA, roles=ROLES, piles=PILES, groups=GROUPS,
        fields=fields,effects=effects,effect_slots=EFFECT_SLOTS,
        effect_width=EFFECT_WIDTH,numbers='known+signed_log; booleans known+raw',
        effect_composition='shared two-layer MLP; ordered slots+presence; dense tanh combiner',
        hierarchy='player/selection separate; other groups mean+max+log1p_count; two-layer tanh state MLP')


@dataclass(frozen=True, slots=True)
class CompactFeatures(StudyFeatures):
    richness: str = 'context'
    typed: dict = None
    roles: np.ndarray = None
    piles: np.ndarray = None
    effects: np.ndarray = None
    effect_owners: np.ndarray = None
    effect_positions: np.ndarray = None

    @property
    def nbytes(self):
        arrays=[self.identities,self.parents,self.candidates,self.roles,self.piles,
                self.effects,self.effect_owners,self.effect_positions]
        arrays += [a for pair in self.typed.values() for a in pair]
        return sum(a.nbytes for a in arrays) + (0 if self.values is None else self.values.nbytes)

    def for_rollout(self):
        return replace(self, graph=None, values=None)


def compact(state, richness):
    names=tuple(n for _,n in channels(richness)); indexes={n:i for i,n in enumerate(names)}
    fields,effect_fields=layout(richness)
    values=state.values
    role_bits=values[:,[indexes['role='+r] for r in ROLES]]
    if not np.all(role_bits.sum(1)==1):
        raise ValueError('Compact entities require one public role')
    roles=role_bits.argmax(1).astype(np.int64)
    pile_bits=values[:,[indexes['pile='+p] for p in PILES]]
    if np.any(pile_bits.sum(1)>1):
        raise ValueError('Ambiguous public pile')
    piles=np.where(pile_bits.sum(1),pile_bits.argmax(1),-1).astype(np.int64)
    typed={}
    for i,role in enumerate(ROLES):
        rows=np.flatnonzero(roles==i)
        allowed=[n.startswith(('role=','pile=')) or _allowed(n,role) or
                 role in ('card','potion','relic') and n.startswith('mechanics.effect.') for n in names]
        if np.any(values[rows][:,np.logical_not(allowed)]):
            raise ValueError('Unmapped compact public field for '+role)
        indexes_scale=fields[role]
        v=values[rows][:,[indexes[n] for n,_ in indexes_scale]]
        v=v*np.asarray([scale for _,scale in indexes_scale],dtype=np.float32)
        typed[role]=(rows,v.astype(np.float32))
    effects=[]; owners=[]; positions=[]
    if effect_fields:
        for slot in range(EFFECT_SLOTS):
            prefix=f'mechanics.effect.{slot}.'
            rows=np.flatnonzero(values[:,indexes[prefix+'present.scaled']]>0)
            if len(rows):
                effects.extend(values[rows][:,[indexes[prefix+n] for n,_ in effect_fields]] *
                               np.asarray([scale for _,scale in effect_fields],dtype=np.float32))
                owners.extend(rows); positions.extend([slot]*len(rows))
    return CompactFeatures(**{name:getattr(state,name) for name in StudyFeatures.__dataclass_fields__},
        richness=richness,typed=typed,roles=roles,piles=piles,
        effects=np.asarray(effects,dtype=np.float32).reshape(-1,len(effect_fields)) if effect_fields else np.empty((0,0),np.float32),
        effect_owners=np.asarray(owners,dtype=np.int64),effect_positions=np.asarray(positions,dtype=np.int64))


class CompactEncoder(StudyEncoder):
    def _encode(self, decision, mapping):
        return compact(super()._encode(decision,mapping),self.spec.richness)

    def encode_inference(self, decision):
        # Keep transient audit rows for StudyPolicy, without retaining its graph.
        owner=f.PreparedPublic(decision)
        mapping=self.public.mapping_prepared(owner.value,owner)
        return replace(self._encode(decision,mapping),graph=None)


def collate_compact(states,vocabulary):
    if (not states or any(type(s) is not CompactFeatures or s.vocabulary!=vocabulary.identity for s in states)
            or len({(s.feature_identity,s.capacity,s.richness,s.action_policy) for s in states})!=1):
        raise ValueError('Mixed compact feature semantics')
    fields,ef=layout(states[0].richness)
    rows={r:[] for r in ROLES}; ids={r:[] for r in ROLES}
    owners=[]; roles=[]; groups=[]; effects=[]; effect_owners=[]; effect_positions=[]
    n=len(states); a=max(len(s.candidates) for s in states)
    candidates=np.full((n,a,3),-1,dtype=np.int64); mask=np.zeros((n,a),bool)
    offset=0
    for b,s in enumerate(states):
        size=len(s.roles); count=len(s.candidates)
        if (not 0<size<=s.capacity or s.roles.dtype!=np.int64 or s.roles.shape!=(size,)
                or np.any((s.roles<0)|(s.roles>=len(ROLES))) or s.roles[0]!=ROLES.index('player')
                or np.count_nonzero(s.roles==ROLES.index('player'))!=1
                or np.count_nonzero(s.roles==ROLES.index('selection'))>1
                or s.piles.shape!=(size,) or s.piles.dtype!=np.int64
                or np.any((s.piles < -1)|(s.piles>=len(PILES)))
                or np.any((s.piles>=0)&(s.roles!=ROLES.index('card')))
                or s.identities.shape!=(size,) or np.any(s.identities)
                or s.candidates.shape!=(count,3) or s.candidates.dtype!=np.int64
                or count<1 or count>2048 or len(s.candidate_refs)!=count or len(set(s.candidate_refs))!=count
                or len(s.policy_mask)!=count or len(s.legal_mask)!=count or not any(s.policy_mask)
                or any(type(v) is not bool for v in (*s.policy_mask,*s.legal_mask))
                or any(p and not l for p,l in zip(s.policy_mask,s.legal_mask))
                or np.any((s.candidates[:,0]<0)|(s.candidates[:,0]>=len(f.ACTIONS)))
                or np.any((s.candidates[:,1:] < -1)|(s.candidates[:,1:]>=size))):
            raise ValueError('Invalid compact entities or candidates')
        if set(s.typed)!=set(ROLES):
            raise ValueError('Missing compact role')
        for r in ROLES:
            ix,v=s.typed[r]; expected=np.flatnonzero(s.roles==ROLES.index(r))
            if (ix.dtype!=np.int64 or not np.array_equal(ix,expected) or
                    v.shape!=(len(ix),len(fields[r])) or v.dtype!=np.float32 or not np.isfinite(v).all()):
                raise ValueError('Invalid typed entity fields')
            rows[r].append(v); ids[r].append(ix+offset)
        m=len(s.effects)
        if (s.effects.shape!=(m,len(ef)) or s.effects.dtype!=np.float32 or not np.isfinite(s.effects).all()
                or s.effect_owners.shape!=(m,) or s.effect_positions.shape!=(m,)
                or s.effect_owners.dtype!=np.int64 or s.effect_positions.dtype!=np.int64
                or np.any((s.effect_owners<0)|(s.effect_owners>=size))
                or np.any((s.effect_positions<0)|(s.effect_positions>=EFFECT_SLOTS))
                or len(set(zip(s.effect_owners.tolist(),s.effect_positions.tolist())))!=m
                or any(ROLES[i] not in ('card','potion','relic') for i in s.roles[s.effect_owners])):
            raise ValueError('Invalid effect ownership/order')
        owners.extend([b]*size); roles.extend(s.roles)
        groups.extend(GROUPS.index('card:'+('none' if p<0 else PILES[p])) if ROLES[r]=='card'
                      else GROUPS.index(ROLES[r]) for r,p in zip(s.roles,s.piles))
        effects.append(s.effects); effect_owners.append(s.effect_owners+offset); effect_positions.append(s.effect_positions)
        candidates[b,:count]=s.candidates
        candidates[b,:count,1:]=np.where(s.candidates[:,1:]>=0,s.candidates[:,1:]+offset,-1)
        mask[b,:count]=s.policy_mask
        offset+=size
    values=dict(candidates=candidates,mask=mask,owners=np.asarray(owners,np.int64),
        roles=np.asarray(roles,np.int64),groups=np.asarray(groups,np.int64),
        effects=np.concatenate(effects),effect_owners=np.concatenate(effect_owners),
        effect_positions=np.concatenate(effect_positions))
    for r in ROLES:
        values['typed_'+r]=np.concatenate(rows[r]); values['indexes_'+r]=np.concatenate(ids[r])
    return {**{k:torch.from_numpy(v) for k,v in values.items()},'feature_identity':states[0].feature_identity}


class CompactNetwork(nn.Module):
    def __init__(self,architecture):
        super().__init__()
        self.hierarchical=architecture.kind=='hierarchical_pooled_mlp'
        self.spec=FeatureSpec.from_dict(architecture.features)
        fields,ef=layout(self.spec.richness); d=architecture.hidden_size
        self.width=d; self.has_effects=bool(ef)
        if self.has_effects:
            self.effect=nn.Sequential(nn.Linear(len(ef),EFFECT_WIDTH),nn.Tanh(),
                                      nn.Linear(EFFECT_WIDTH,EFFECT_WIDTH),nn.Tanh())
            self.ordered=nn.Sequential(nn.Linear(EFFECT_SLOTS*(EFFECT_WIDTH+1),d),nn.Tanh())
        self.inputs=nn.ModuleDict({r:nn.Linear(len(fields[r])+(d if self.has_effects and r in ('card','potion','relic') else 0),d)
                                  for r in ROLES})
        self.layers=nn.ModuleList(nn.Linear(d,d) for _ in range(2))
        if self.hierarchical:
            width=2*d+1+(len(GROUPS)-2)*(2*d+1)
            self.state=nn.Sequential(nn.Linear(width,d),nn.Tanh(),nn.Linear(d,d),nn.Tanh())
        self.scorer=nn.Sequential(nn.Linear(3*d+len(f.ACTIONS)+2,d),nn.Tanh(),nn.Linear(d,1))
        self.value=nn.Linear(d,1)

    def forward(self,batch):
        owner=batch['owners']; n=len(batch['mask']); size=len(owner); d=self.width
        h=batch['typed_player'].new_zeros((size,d))
        if self.has_effects:
            e=self.effect(batch['effects'])
            ordered=e.new_zeros((size,EFFECT_SLOTS,EFFECT_WIDTH))
            present=e.new_zeros((size,EFFECT_SLOTS))
            ordered[batch['effect_owners'],batch['effect_positions']]=e
            present[batch['effect_owners'],batch['effect_positions']]=1
            mechanics=self.ordered(torch.cat((ordered.flatten(1),present),-1))
        for role in ROLES:
            ix=batch['indexes_'+role]; v=batch['typed_'+role]
            if self.has_effects and role in ('card','potion','relic'):
                v=torch.cat((v,mechanics[ix]),-1)
            h=h.index_copy(0,ix,torch.tanh(self.inputs[role](v)))
        for layer in self.layers:
            h=torch.tanh(layer(h))
        if self.hierarchical:
            g=len(GROUPS); indexes=owner*g+batch['groups']
            total=h.new_zeros((n*g,d)).index_add(0,indexes,h)
            counts=h.new_zeros(n*g).index_add(0,indexes,h.new_ones(size))
            mean=(total/counts.clamp_min(1)[:,None]).reshape(n,g,d)
            maximum=h.new_full((n*g,d),-torch.inf).scatter_reduce(0,indexes[:,None].expand(-1,d),h,reduce='amax')
            maximum=torch.where(counts[:,None]>0,maximum,0).reshape(n,g,d)
            count=counts.reshape(n,g)
            grouped=torch.cat((mean[:,2:],maximum[:,2:],torch.log1p(count[:,2:])[...,None]),-1).flatten(1)
            state=self.state(torch.cat((mean[:,0],mean[:,1],count[:,1:2],grouped),-1))
        else:
            state=h.new_zeros((n,d)).index_add(0,owner,h)
            count=h.new_zeros(n).index_add(0,owner,h.new_ones(size))
            state=state/count[:,None].clamp_min(1)
        a=batch['candidates']; exists=(a[:,:,1:]>=0).to(h.dtype)
        operands=[h[a[:,:,i].clamp_min(0)]*exists[:,:,i-1:i] for i in (1,2)]
        action=torch.nn.functional.one_hot(a[:,:,0].clamp_min(0),len(f.ACTIONS)).to(h.dtype)
        x=torch.cat((state[:,None].expand(-1,a.shape[1],-1),*operands,action,exists),-1)
        return self.scorer(x).squeeze(-1),self.value(state).squeeze(-1)
