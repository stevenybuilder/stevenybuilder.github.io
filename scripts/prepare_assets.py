"""Build website figures from archived measurements, and repackage existing video.

Usage: .venv/bin/python scripts/prepare_assets.py /path/to/research-archive
No model inference, fabricated activations, or generated simulator imagery.
"""
import csv
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1])
DATA = ROOT / 'assets/data'
MEDIA = ROOT / 'assets/media'
DATA.mkdir(parents=True, exist_ok=True)
MEDIA.mkdir(parents=True, exist_ok=True)
receipts = []

def source(rel):
    p = SRC / rel
    receipts.append({'path': rel, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    return p

def rows(rel):
    return list(csv.DictReader(source(rel).open()))

def save(name, data):
    (DATA / name).write_text(json.dumps(data, separators=(',', ':'), allow_nan=False))

dose_rows = rows('figures/00_position_dose_hero.csv')
doses = []
for n in sorted({int(r['n_pos']) for r in dose_rows}):
    obj = {'positions': n}
    for arm, key in [('LOC', 'selected'), ('RAND', 'random')]:
        subset = [r for r in dose_rows if int(r['n_pos']) == n and r['arm'] == arm]
        obj[key] = statistics.median(float(r['R']) for r in subset)
        # These are descriptive scene-direction aggregates, not independent trials.
        cells = {r['cell']: float(r['cell_median_R']) for r in subset}
        obj[key + '_cells'] = list(cells.values())
    doses.append(obj)
save('dose.json', doses)
(DATA / 'position-dose.csv').write_text(source('figures/00_position_dose_hero.csv').read_text())

probe_rows = rows('figures/02a_layer_probe_accuracy.csv')
probes = [{'layer': int(r['layer']), 'segment': r['segment'], 'accuracy': float(r['accuracy'])} for r in probe_rows]
causal_rows = rows('figures/02c_causal_repair_cells.csv')
causal = {c: statistics.median(float(r['repair_R']) for r in causal_rows if r['condition'] == c)
          for c in sorted({r['condition'] for r in causal_rows})}
save('readable.json', {'probes': probes, 'causal': causal})
(DATA / 'probe-accuracy.csv').write_text(source('figures/02a_layer_probe_accuracy.csv').read_text())
(DATA / 'causal-repair.csv').write_text(source('figures/02c_causal_repair_cells.csv').read_text())

episodes_path = source('artifacts/pi05_instruction_repair_2026-08-31/state_confirm/episodes.jsonl')
episodes = [json.loads(line) for line in episodes_path.read_text().splitlines() if line.strip()]
rollouts = {c: {'successes': sum(bool(r['success']) for r in episodes if r['condition'] == c),
                'total': sum(r['condition'] == c for r in episodes)}
            for c in sorted({r['condition'] for r in episodes})}
assert rollouts['state_live'] == {'successes':18, 'total':20}
save('rollout-counts.json', rollouts)

# A separate archival dataset: mean image residuals entering prefix layers 12–17,
# concatenated (6 * 2048 dimensions), captured before movement on 800 episodes.
# PCA uses no labels; color changes do not move points or refit the projection.
npz = np.load(source('artifacts/obedience_probe_feats.npz'), allow_pickle=False)
X = npz['X_img'].astype(np.float64)
X -= X.mean(axis=0, keepdims=True)
gram = X @ X.T
values, vectors = np.linalg.eigh(gram)
order = np.argsort(values)[::-1]
values = np.maximum(values[order], 0)
vectors = vectors[:, order[:2]]
for j in range(2):
    if vectors[np.argmax(np.abs(vectors[:, j])), j] < 0:
        vectors[:, j] *= -1
xy = vectors * np.sqrt(values[:2])
points = [{'x': round(float(p[0]), 5), 'y': round(float(p[1]), 5),
           'scene': int(s), 'outcome': int(y), 'cell': str(c)}
          for p,s,y,c in zip(xy, npz['scene'], npz['y'], npz['cells'])]
geometry = {'method': 'PCA on globally centered concatenated mean image residuals entering layers 12–17; no scaling or whitening',
            'n': len(X), 'dimensions': X.shape[1],
            'explained': (values[:2] / values.sum()).tolist(), 'points': points,
            'outcomes': {'0':'Scene target first', '1':'Prompt target first', '2':'Neither target first'}}
save('geometry.json', geometry)

plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':12, 'axes.spines.top':False,
                    'axes.spines.right':False, 'axes.labelcolor':'#282a25',
                    'text.color':'#282a25', 'axes.edgecolor':'#c8c8bf', 'svg.fonttype':'none'})
fig, ax = plt.subplots(figsize=(10,5.1), layout='constrained')
for key,col,label in [('selected','#24796c','Object-centered'),('random','#c27729','Count-matched random')]:
    ax.plot(range(8),[r[key] for r in doses],color=col,linewidth=2.7,marker='o',label=label)
ax.axhline(1, color='#afb4aa', linewidth=1, linestyle='--')
ax.set(xticks=range(8), xticklabels=[r['positions'] for r in doses], ylim=(-.03,1.06),
       xlabel='Image positions replaced (of 512)', ylabel='Action progress toward donor, R')
ax.grid(axis='y', alpha=.15)
ax.legend(frameon=False, loc='upper left')
fig.savefig(MEDIA/'position-dose.svg')
fig.savefig(MEDIA/'position-dose.png',dpi=180)
plt.close(fig)

fig, ax = plt.subplots(figsize=(9,5.5),layout='constrained')
for s in sorted(set(npz['scene'])):
    m=npz['scene']==s
    ax.scatter(xy[m,0],xy[m,1],s=14,alpha=.6,label=f'Scene {s}')
ax.set(xlabel=f'PC1 ({geometry["explained"][0]:.1%} variance)',ylabel=f'PC2 ({geometry["explained"][1]:.1%} variance)')
ax.legend(frameon=False,fontsize=9,ncol=2)
fig.savefig(MEDIA/'geometry.svg')
plt.close(fig)

# Remove titles baked into the existing four-panel montage. Native scene tiles
# are 300px; Lanczos resampling improves presentation, not information content.
video = source('media/videos/state-confirmation/combined.mp4')
meta = json.loads(source('media/videos/state-confirmation/meta.json').read_text())
for i,name in enumerate(['conflict','correct','repair','early']):
    crop=f'crop=300:300:{22+312*i}:157,scale=600:600:flags=lanczos,setsar=1'
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(video),
                    '-vf',crop,'-an','-c:v','libx264','-crf','18','-preset','slow',
                    '-pix_fmt','yuv420p','-movflags','+faststart',str(MEDIA/f'{name}.mp4')],check=True)
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(MEDIA/f'{name}.mp4'),
                    '-frames:v','1',str(MEDIA/f'{name}.jpg')],check=True)
save('video-provenance.json', {'source': receipts[-2], 'capture':meta,
    'transform':'Crop each 300×300 scene tile from published montage; Lanczos resize to 600×600; H.264 CRF18; no frame interpolation or generated detail.',
    'timing':'Original montage samples every second simulator frame at 30 fps; displayed at 0.5x for 30 simulator steps per wall-clock second. Successful runs freeze at completion.'})
save('sources.json', {'inputs':receipts, 'geometry_note':'New descriptive visualization of archived features. No causal inference follows from the projection.'})

band_rows = [r for r in rows('figures/00b_layerwise_model_biology_hero.csv') if r['panel']=='causal_bands']
bands = {b:[float(r['value']) for r in band_rows if r['band']==b] for b in ['0-5','6-11','12-17']}
save('layer-bands.json', bands)
fig, ax=plt.subplots(figsize=(9,4.4),layout='constrained')
for i,(b,vs) in enumerate(bands.items()):
    ax.scatter(np.linspace(i-.08,i+.08,len(vs)),vs,s=27,facecolors='none',edgecolors='#4e6fa5',alpha=.7)
ax.plot(range(3),[statistics.median(v) for v in bands.values()],color='#4e6fa5',marker='o',linewidth=2)
ax.set(xticks=range(3),xticklabels=['0–5','6–11','12–17'],xlabel='Prefix layers replaced',ylabel='Action progress, R',ylim=(-.04,1.1))
ax.grid(axis='y',alpha=.15)
fig.savefig(MEDIA/'layer-bands.svg');plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(10,4.4),layout='constrained',sharey=True)
for ax,key,col,title in zip(axes,['selected','random'],['#24796c','#b67930'],['Object-centered','Count-matched random']):
    for k in range(8):
        ax.plot(range(8),[r[key+'_cells'][k] for r in doses],color=col,alpha=.3,linewidth=1)
    ax.plot(range(8),[r[key] for r in doses],color=col,linewidth=2.6)
    ax.set(title=title,xticks=[0,3,5,6,7],xticklabels=[4,32,128,256,512],xlabel='Positions replaced')
    ax.grid(axis='y',alpha=.12)
axes[0].set_ylabel('Action progress, R')
fig.savefig(MEDIA/'dose-cells.svg');plt.close(fig)

units=sorted({(r['task_id'],r['init_id']) for r in episodes})
conditions=['correct','conflict','state_live','state_early']
case_data=[{'task':t,'init':i,'success':{c:next(bool(r['success']) for r in episodes if (r['task_id'],r['init_id'],r['condition'])==(t,i,c)) for c in conditions}} for t,i in units]
save('rollout-cases.json',case_data)
fig,ax=plt.subplots(figsize=(10,3.5),layout='constrained')
colors=['#24796c','#b05443','#4e6fa5','#b67930']
for y,(c,color) in enumerate(zip(conditions,colors)):
    for x,case in enumerate(case_data):
        ax.scatter(x,y,marker='s',s=110,color=color if case['success'][c] else '#ebede7',edgecolors='none')
ax.set(yticks=range(4),yticklabels=['Correct prompt','Conflicting prompt','Late repair','Early control'],xticks=[0,9,10,19],xticklabels=['1','10','11','20'],xlabel='Matched task/state case',ylim=(3.7,-.7))
for s in ax.spines.values():s.set_visible(False)
ax.tick_params(length=0)
fig.savefig(MEDIA/'rollout-cases.svg');plt.close(fig)

side_path=source('artifacts/pi05_state_repair_side_effects_2026-09-04_v1/episodes.jsonl')
side=[json.loads(l) for l in side_path.read_text().splitlines() if l.strip()]
side_units=sorted({(r['task_id'],r['init_id']) for r in side})
side_conditions=sorted({r['condition'] for r in side})
repair_condition='repair_live'
side_out=[]
fig,ax=plt.subplots(figsize=(8,4.3),layout='constrained')
for n,(t,i) in enumerate(side_units):
    clean=next(r for r in side if (r['task_id'],r['init_id'],r['condition'])==(t,i,'clean_correct'))
    repair=next(r for r in side if (r['task_id'],r['init_id'],r['condition'])==(t,i,repair_condition))
    item={'task':t,'init':i,'clean_steps':clean['n_steps'],'repair_steps':repair['n_steps'],'repair_success':repair['success']}
    side_out.append(item)
    ax.plot([0,1],[clean['n_steps'],repair['n_steps']],color='#afb7b0',alpha=.65,linewidth=1.2)
    ax.scatter(0,clean['n_steps'],color='#24796c',s=30)
    ax.scatter(1,repair['n_steps'],color='#4e6fa5' if repair['success'] else '#b05443',marker='o' if repair['success'] else 'x',s=40)
ax.set(xticks=[0,1],xticklabels=['Correct prompt','Late repair'],ylabel='Episode duration (simulator steps)',xlim=(-.35,1.35))
ax.grid(axis='y',alpha=.15)
fig.savefig(MEDIA/'side-effects.svg');plt.close(fig)
save('side-effects.json',side_out)
save('trajectories.json',{c:next(r['eef_path'] for r in episodes if r['task_id']==1 and r['init_id']==20 and r['condition']==c) for c in conditions})
save('sources.json', {'inputs':receipts, 'geometry_note':'New descriptive visualization of archived features. No causal inference follows from the projection.'})
print(json.dumps({'dose_512':doses[-1], 'rollouts':rollouts,'pca_variance':geometry['explained'], 'causal':causal},indent=2))
