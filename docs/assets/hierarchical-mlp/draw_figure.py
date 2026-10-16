"""Paper-style diagram of the experimental typed combat encoder.

Run with matplotlib. Writes editable SVG, PDF, and PNG beside this script.
The design is informed by OpenAI Five Figure 17 (https://cdn.openai.com/dota-2.pdf).
The experiment manifest records exact dimensions, settings and implementation.
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from matplotlib.path import Path as MplPath

OUT = Path(__file__).resolve().parent
W, H = 1440, 1760
plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 13.5,
    'svg.fonttype': 'none', 'pdf.fonttype': 42,
    'savefig.facecolor': 'white', 'figure.facecolor': 'white',
})
fig = plt.figure(figsize=(14.4, 17.6))
ax = fig.add_axes((0, 0, 1, 1))
ax.set(xlim=(0, W), ylim=(H, 0))
ax.axis('off')
C = dict(ink='#253044', muted='#596579', line='#647185', raw='#fff1c9',
         encoder='#dcebd6', vector='#dae8f9', pool='#ece1f4',
         bank='#34719c', pale='#f7f8fa', rule='#dce1e6')
artists = []

def text(x, y, s, *, size=13.5, weight='normal', color=None,
         ha='center', va='center', linespacing=1.45, **kw):
    t = ax.text(x, y, s, fontsize=size, fontweight=weight, color=color or C['ink'],
                ha=ha, va=va, linespacing=linespacing, zorder=6, **kw)
    artists.append(t)
    return t

def box(x, y, w, h, title, body='', *, fill='raw', title_size=14,
        body_size=12.5, edge=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=9',
                 linewidth=1.15, edgecolor=edge or C['line'],
                 facecolor=C.get(fill, fill), zorder=3))
    if body:
        text(x+w/2, y+24, title, size=title_size, weight='bold')
        text(x+w/2, y+49, body, size=body_size, va='top', linespacing=1.38)
    else:
        text(x+w/2, y+h/2, title, size=title_size, weight='bold')
    return (x, y, w, h)

def line(points, *, arrow=False, dashed=False, color=None, lw=1.6):
    points = list(points)
    path = MplPath(points, [MplPath.MOVETO]+[MplPath.LINETO]*(len(points)-1))
    patch = FancyArrowPatch(path=path, arrowstyle='-|>' if arrow else '-',
                            mutation_scale=13, linewidth=lw,
                            linestyle=(0,(4,3)) if dashed else '-',
                            color=color or C['line'], zorder=2,
                            capstyle='round', joinstyle='round')
    ax.add_patch(patch)

def dot(x,y,color=None):
    ax.add_patch(Circle((x,y), radius=3, facecolor=color or C['line'],
                       edgecolor='none', zorder=4))

def panel(y, letter, title):
    text(48,y,letter,size=18,weight='bold',ha='left')
    text(80,y,title,size=18,weight='bold',ha='left')

text(48,39,'Hierarchical pooled MLP',size=25,weight='bold',ha='left')
text(48,77,'Public combat observations → structured encoding → policy and value',
     size=14.5,color=C['muted'],ha='left')
text(1389,40,'EXPERIMENTAL',size=12,weight='bold',ha='right',color=C['muted'])
text(1389,69,'No content vocabulary',size=12,ha='right',color=C['muted'])

for x,label,key in [(48,'Public inputs','raw'),(300,'Shared encoders','encoder'),
                    (590,'Learned vectors','vector'),(870,'Pooling / heads','pool')]:
    ax.add_patch(FancyBboxPatch((x,110),22,16,boxstyle='round,pad=0,rounding_size=3',
                  facecolor=C[key],edgecolor=C['line'],linewidth=.8,zorder=3))
    text(x+33,118,label,size=12.5,ha='left')
line([(1160,118),(1205,118)],dashed=True,color=C['bank'])
text(1217,118,'Retained entities',size=12.5,ha='left')

panel(163,'a','Typed observation processing')
xs = [48,381,714,1047]
bw=285
centers=[x+bw/2 for x in xs]
raw=[
 ('Player & global context','HP · block · resources · powers\nCounters · threat · choice state'),
 ('Cards, grouped by pile','Current cost · type · modifiers\nPublic printed effects [E]'),
 ('Enemies','HP · block · displayed intent\nOwned powers · recent history'),
 ('Potions & relics','Availability · public counters\nPublic effect descriptions [E]'),
]
enc=[
 ('Context / entity encoders','Separate typed inputs'),
 ('Shared card encoder','Same weights for every card'),
 ('Shared enemy encoder','History stays with its enemy'),
 ('Typed item encoders','Shared within potion / relic type'),
]
vec=[
 ('Globals + entity tokens','Player / selection operands'),
 ('Card embeddings','Ncards × d'),
 ('Enemy embeddings','Nenemies × d'),
 ('Item embeddings','Nitems × d'),
]
pool=[
 ('Keep context separate','Globals · player · selection'),
 ('Separate pool for each pile','Hand · draw · discard · exhaust\nOffered · in-play · sequestered'),
 ('Enemy pool','Living / present masks retained'),
 ('Separate item pools','Potions and relics'),
]
for i,x in enumerate(xs):
    box(x,194,bw,105,*raw[i],title_size=13.1,body_size=11.8)
    box(x,337,bw,79,*enc[i],fill='encoder',title_size=13.1,body_size=11.7)
    box(x,451,bw,73,*vec[i],fill='vector',title_size=12.6,body_size=11.8)
    box(x,574,bw,94,*pool[i],fill='pool',title_size=12.9,body_size=11.4)
    cx=centers[i]
    line([(cx,299),(cx,337)],arrow=True)
    line([(cx,416),(cx,451)],arrow=True)
    line([(cx,524),(cx,574)],arrow=True)
    line([(cx,668),(cx,704)])
    dot(cx,548,C['bank'])

# The blue bypass preserves addressable objects for subject/target gathering.
line([(centers[0],548),(1391,548),(1391,1280),(1332,1280)],
     dashed=True,arrow=True,color=C['bank'],lw=1.8)

line([(centers[0],704),(centers[-1],704)])
dot(720,704)
line([(720,704),(720,735)],arrow=True)
box(463,735,514,55,'Concatenate globals and group summaries',fill='pool',title_size=14)
line([(720,790),(720,823)],arrow=True)
box(505,823,430,55,'Nonlinear state MLP → state vector z',fill='encoder',title_size=14)
text(720,903,'Collection pools use mean + max + log-count.  State / entity width d = 64.',
     size=12,color=C['muted'])

ax.plot([48,1350],[931,931],color=C['rule'],lw=1,zorder=1)
panel(961,'b','Shared mechanics module [E] — used inside card and item encoders')
box(48,995,345,118,'Effect records',
    'Kind · trigger · target · duration\nAmount · hits · expression\nKnown / applicability flags',
    title_size=14,body_size=11.7)
box(437,995,240,118,'Shared effect MLP',
    'Same weights for\nevery effect record',fill='encoder',title_size=13.3,body_size=12)
box(721,995,291,118,'Ordered combination',
    'Preserve effect sequence\nand dependencies',fill='encoder',title_size=13.5,body_size=12)
box(1056,995,276,118,'Mechanics vector',
    'Into its owning\ncard / item encoder',fill='vector',title_size=13.5,body_size=12)
for left,right in [(393,437),(677,721),(1012,1056)]:
    line([(left,1051),(right,1051)],arrow=True)
text(720,1138,'Mechanical categories use fixed one-hot fields; content names and content IDs are excluded.',
     size=12,color=C['muted'])

ax.plot([48,1350],[1166,1166],color=C['rule'],lw=1,zorder=1)
panel(1196,'c','Policy and value heads')
box(48,1241,320,79,'State vector z','From the state MLP in (a)',
    fill='vector',title_size=14,body_size=12)
box(473,1241,337,79,'Legal candidate table','Action type · subject / target refs',
    title_size=14,body_size=11.7)
box(955,1241,377,79,'Retained entity embeddings','From (a), including offered choices',
    fill='vector',title_size=13.7,body_size=11.7,edge=C['bank'])

box(805,1375,377,79,'Gather candidate operands','Subject / target embeddings + action',
    fill='vector',title_size=13.5,body_size=11.5)
line([(641.5,1320),(641.5,1347),(993.5,1347),(993.5,1375)],arrow=True)
line([(1143.5,1320),(1143.5,1347),(993.5,1347)])
dot(993.5,1347)

box(805,1496,377,67,'Shared candidate scorer',fill='encoder',title_size=14)
line([(993.5,1454),(993.5,1496)],arrow=True)
line([(368,1280),(420,1280),(420,1529.5),(805,1529.5)],arrow=True)
text(590,1511,'same state z for each candidate',size=11.7,color=C['muted'])

box(48,1390,320,67,'Value head',fill='pool',title_size=14)
line([(208,1320),(208,1390)],arrow=True)
box(48,1530,320,81,'State value V(s)','Both heads see offered choices',
    fill='white',title_size=15,body_size=11.7)
line([(208,1457),(208,1530)],arrow=True)

box(473,1610,253,79,'Candidate masks','Legal / policy constraints',
    title_size=13.5,body_size=11.6)
box(805,1610,377,79,'Masked softmax → π(a | s)','Distribution over candidate actions',
    fill='pool',title_size=14,body_size=11.7)
line([(993.5,1563),(993.5,1610)],arrow=True)
line([(726,1649.5),(805,1649.5)],arrow=True)

text(48,1731,'Experimental architecture; see the study record for evidence.  Layout inspired by OpenAI Five, Fig. 17.',
     size=11.6,color=C['muted'],ha='left')

# Verify that all labels remain inside the figure, then export vector + raster.
fig.canvas.draw()
renderer=fig.canvas.get_renderer()
canvas=fig.bbox
for artist in artists:
    bounds=artist.get_window_extent(renderer)
    assert bounds.x0 >= canvas.x0 and bounds.x1 <= canvas.x1, artist.get_text()
    assert bounds.y0 >= canvas.y0 and bounds.y1 <= canvas.y1, artist.get_text()
for ext in ('svg','pdf','png'):
    path = OUT / f'design.{ext}'
    fig.savefig(path,dpi=180)
    if ext == 'svg':
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
print(OUT / 'design.png')
