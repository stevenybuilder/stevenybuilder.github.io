"""Restore selected report paragraphs verbatim, keeping existing data figures."""
import sys, re, html, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

root = Path(__file__).resolve().parents[1]
with zipfile.ZipFile(sys.argv[1]) as z:
    document = ET.fromstring(z.read('word/document.xml'))
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
paras = [''.join(p.itertext()) for p in []]
paras = [''.join(p.findall('.//w:t', ns)[i].text or '' for i in range(len(p.findall('.//w:t', ns)))).strip() for p in document.findall('.//w:body/w:p', ns)]
def paragraph(start):
    matches = [p for p in paras if p.startswith(start)]
    if len(matches) != 1:
        raise ValueError((start, len(matches)))
    text = html.escape(matches[0])
    text = text.replace('Jim Fan 2026', '<a href="https://x.com/DrJimFan/status/2018754323141054786">Jim Fan 2026</a>')
    for name, paper in [('Nanda et al.', '2309.00941'), ('Casademunt et al', '2507.16795'), ('Miao et al', '2605.17144')]:
        text = text.replace(name, f'<a href="https://arxiv.org/abs/{paper}">{name}</a>')
    return '<p data-report-verbatim>' + text + '</p>'
old = (root/'content/pick-it-up.html').read_text()
def figure(n):
    match = re.search(r'<figure\b[^>]*id="figure-'+str(n)+r'"[\s\S]*?</figure>', old)
    if not match: raise ValueError(n)
    result = match.group()
    result = re.sub(r'<b>Figure \d+\.</b>\s*','',result)
    result = re.sub(r'<span class="figure-index">\d+</span>','',result)
    return result.replace('used in Figure 1','used in the main dose curve').replace('id="causal-chart" viewBox="0 0 360 310"','id="causal-chart" viewBox="0 0 430 310"')
def section(id, title, body):
    return f'<section id="{id}"><div class="prose"><h2>{title}</h2></div>{body}</section>'
def prose(*starts): return '<div class="prose">'+''.join(paragraph(s) for s in starts)+'</div>'
parts = []
parts.append(section('question','What problem am I trying to solve?',prose('I investigated whether','I hypothesized that')))
parts.append(section('importance','Why is this important?',prose('Fine-grained control','These steering methods','Most of all, LLMs')))
parts.append(section('rollouts','Key Experiments',prose('As shown in the first graph above')+figure(1)))
parts.append(section('language','Readable language was not controlling behavior',prose('Conversely, editing text')+figure(6)))
parts.append(section('background','Model biology for physical AI',prose('Dissecting the model biology')+figure(10)))
parts.append(section('geometry','Representation geometry',prose('However, VLAs and world models')+figure(9)))
# Condense by selecting whole original sentences, never paraphrasing them.
limit_a = next(p for p in paras if p.startswith('Because I only had two tasks'))
limit_b = next(p for p in paras if p.startswith('In the future, we could'))
limit_b = limit_b.split(' And add validation')[0]
limit_c = next(p for p in paras if p.startswith('Perhaps the highest ROI'))
limit_c = limit_c.split(' This would also')[0]
parts.append(section('limitations','Future directions','<div class="prose"><p data-report-verbatim>'+html.escape(limit_b+' '+limit_c)+'</p></div>'))
parts.append(section('appendix','Supporting figures',''.join(figure(n) for n in [11,12,13,14])))
refs = old[old.index('<section id="references"'):]
parts.append(refs)
videos=[]
for n in [2,3,4,5]:
    item=figure(n)
    item=re.sub(r'<a href="/assets/media/[^\"]+">MP4</a>','',item)
    item=item.replace('data-sync muted playsinline','data-ambient muted playsinline loop')
    videos.append(item)
hero='<figure class="figure opening-film"><video id="opening-video" muted playsinline loop preload="metadata" poster="/assets/media/repair.jpg"><source src="/assets/media/repair.mp4" type="video/mp4"></video></figure>'
comparison='<div class="rollout-lab" id="rollout-lab"><div class="video-grid four-videos">'+''.join(videos)+'</div></div>'
code='<blockquote class="code-callout"><a href="https://github.com/stevenybuilder/mechinterp-vla">Code found here</a></blockquote>'
parts=[p.replace(figure(1),comparison+code+figure(1)) if p.startswith('<section id="rollouts"') else p for p in parts]
opening=hero
output=opening+'\n'+'\n'.join(parts)+'\n'
output=re.sub(r'\s*(?:·\s*)?<a href="(?:/assets/data/[^\"]+|https://github.com/stevenybuilder/mechinterp-vla/blob/main/numbers%20audit.md)">[^<]*</a>', '', output)
(root/'content/pick-it-up.html').write_text(output)
print('Restored exact report paragraphs; removed prompt cards, flowchart, controls, and collapsed appendix.')
