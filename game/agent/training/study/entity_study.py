"""Frozen compact/hierarchical versus original pooled/flat comparison."""
from dataclasses import asdict, replace
import numpy as np
from ..features import Vocabulary
from .model import parameters
from .spec import StudyArchitecture

SCHEMA='sts_vantom_entity_encoding_study_v1'
DESIGNS=('flat_mlp','pooled_mlp','compact_pooled_mlp','hierarchical_pooled_mlp')
LEVELS=('basic','context')


def configurations(parent,width):
    rows={}
    for kind in DESIGNS:
        for richness in LEVELS:
            baseline='flat_mlp' if kind=='flat_mlp' else 'pooled_mlp'
            old=parent['configurations'][f'{baseline}-mechanical-{richness}']
            model=StudyArchitecture(**old['architecture'])
            if model.kind!=baseline or model.features['identities'] or model.features['ablations'] or model.features['richness']!=richness:
                raise ValueError('Unexpected parent entity comparison features')
            model=replace(model,kind=kind,hidden_size=width)
            vocab=Vocabulary.from_dict(old['vocabulary'])
            name=f'{kind}-mechanical-{richness}'
            rows[name]=dict(architecture=asdict(model),vocabulary=vocab.to_dict(),parameters=parameters(model,vocab))
    return rows


def comparisons():
    return [(f'hierarchical_pooled_mlp-mechanical-{r}',f'{k}-mechanical-{r}')
            for r in LEVELS for k in DESIGNS[:-1]]


def secondary_comparisons():
    return ([(f'{k}-mechanical-context',f'{k}-mechanical-basic') for k in DESIGNS] +
            [(f'compact_pooled_mlp-mechanical-{r}',f'pooled_mlp-mechanical-{r}') for r in LEVELS])


def plots(output,manifest,curves,comparisons):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels=dict(flat_mlp='Flat',pooled_mlp='Original pooled',compact_pooled_mlp='Compact pooled',
                hierarchical_pooled_mlp='Hierarchical pooled')
    fig,axes=plt.subplots(1,2,figsize=(12,4),sharey=True,layout='constrained')
    for ax,richness in zip(axes,LEVELS):
        for kind in DESIGNS:
            rows=curves.get(f'{kind}-mechanical-{richness}',{})
            if not rows: continue
            steps=sorted(next(iter(rows.values())))
            values=np.asarray([[r[s] for s in steps] for r in rows.values()])
            ax.plot(steps,values.mean(0),label=labels[kind])
            ax.fill_between(steps,values.min(0),values.max(0),alpha=.1)
        ax.set(title='Basic' if richness=='basic' else 'Rich (context)',xlabel='Collected decisions',
               ylabel='DEV greedy win rate',ylim=(0,1))
        if ax.lines: ax.legend()
    fig.suptitle('No content vocabulary; width 64; bands show seed ranges')
    fig.savefig(output/'learning-curves.png',dpi=160);plt.close(fig)
    if comparisons:
        fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
        means=np.asarray([c['greedy']['mean'] for c in comparisons])*100
        bounds=np.asarray([c['greedy_family_adjusted']['interval'] for c in comparisons])*100
        ax.errorbar(means,range(len(means)),xerr=np.stack((means-bounds[:,0],bounds[:,1]-means)),fmt='o')
        names=[c['b'].replace('-mechanical-',' / ') for c in comparisons]
        ax.set(yticks=range(len(names)),yticklabels=names,xlabel='Hierarchical minus comparator (DEV percentage points; family-adjusted intervals)')
        ax.axvline(0,color='grey',linestyle='--')
        fig.savefig(output/'architecture-comparisons.png',dpi=160);plt.close(fig)
