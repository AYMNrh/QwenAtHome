"""Regenerate the published figures from retained JSON; does not run inference.

Requires matplotlib. Run from any directory: python benchmarks/plot_results.py
"""
import json
import html
import re
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import ScalarFormatter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'assets'
OUT.mkdir(parents=True, exist_ok=True)
BG, PANEL, INK, MUTED, GRID = '#10151c', '#18212d', '#eef4fb', '#a9b9cc', '#334155'
TEAL, BLUE, GOLD, PINK = '#78e1c4', '#7cb8ff', '#f5c66c', '#f495aa'
plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 11,
    'figure.facecolor': BG, 'axes.facecolor': BG,
    'text.color': INK, 'axes.labelcolor': MUTED,
    'xtick.color': MUTED, 'ytick.color': INK,
    'axes.edgecolor': GRID, 'grid.color': GRID,
    'savefig.facecolor': BG, 'svg.hashsalt': 'QwenAtHome',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.spines.left': False, 'axes.spines.bottom': False,
})


def load(name):
    return json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))


def heading(fig, title, subtitle):
    fig.text(.045, .965, 'QWEN AT HOME  /  RTX 5070 Ti · 16 GB', color=TEAL,
             fontsize=10, weight='bold', va='top')
    fig.text(.045, .915, title, fontsize=24, weight='bold', va='top')
    fig.text(.045, .85, subtitle, fontsize=11, color=MUTED, va='top')


def save(fig, name):
    vector = OUT / (name + '.svg')
    fig.savefig(vector, metadata={'Date': None, 'Creator': 'QwenAtHome benchmark figures'})
    vector.write_text('\n'.join(line.rstrip() for line in vector.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
    fig.savefig(OUT / (name + '.png'), dpi=180, metadata={'Software': 'QwenAtHome benchmark figures'})
    plt.close(fig)


def coding_chart():
    base, q3 = load('Qwen38-benchmark-results.json'), load('Qwen38-Q3-85K-results.json')
    flash, huihui = load('QwenFlash-benchmark-results.json'), load('Huihui-Qwen38-results.json')
    profiles = [
        ('IQ4_XS · ordinary\n32K / Q4 KV', base['profiles']['ordinary'], '#7c8da7'),
        ('IQ4_XS · MTP 3\n32K / Q4 KV', base['profiles']['mtp'], BLUE),
        ('IQ4_XS · MTP + lookup\n32K / Q4 KV', base['profiles']['combined'], TEAL),
        ('Q3_K_XL · MTP 3\n85K / Q4 KV', q3['coding'], '#bdacfa'),
        ('Flash IQ2_XS · Strata\n32K / int8 KV', flash['coding'], GOLD),
        ('Huihui IQ3_S · MTP 3\n32K / Q8 KV', huihui['coding'], '#5cd0e1'),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(16, 8.2), sharey=True)
    fig.subplots_adjust(left=.245, right=.96, top=.73, bottom=.21, wspace=.23)
    heading(fig, 'Fast output still has to be correct',
            'Three focused Python tasks · decode tokens/s · profiles have different precision and context allocations')
    for ax, task, title in zip(axes, ('bugfix', 'multi_function_edit', 'fresh_code'),
                               ('TTL expiry fix', 'CSV module edit', 'Fresh lazy generator')):
        for y, (_, rows, color) in enumerate(profiles):
            group = [r for r in rows if r['task'] == task]
            values = [r['timings']['predicted_per_second'] for r in group]
            value, passed = median(values), sum(r['passed'] for r in group)
            bad = passed < len(group)
            ax.barh(y, value, height=.51, color=PINK if bad else color,
                    hatch='///' if bad else None, edgecolor=BG, linewidth=0)
            if len(values) > 1:
                ax.errorbar(value, y, xerr=[[value-min(values)], [max(values)-value]],
                            fmt='none', ecolor=INK, capsize=3, linewidth=1.3)
            # Labels stay beyond the measured range, not over the uncertainty line.
            ax.text(max(values)+5, y, f'{value:.0f}  {passed}/{len(group)}',
                    va='center', fontsize=10, color=PINK if bad else INK)
        ax.set_title(title, loc='left', color=INK, fontsize=14, weight='bold', pad=18)
        ax.set_xlim(0, 290)
        ax.set_xticks([0, 100, 200])
        ax.set_xlabel('Decode tokens/s', labelpad=10)
        ax.set_yticks(range(len(profiles)), [p[0] for p in profiles], fontsize=10)
        ax.tick_params(axis='both', length=0, pad=9)
        ax.grid(axis='x', alpha=.5)
        ax.set_axisbelow(True)
    axes[0].invert_yaxis()
    fig.legend(handles=[Patch(facecolor=PINK, hatch='///', label='At least one failed check; speed does not imply correct code')],
               loc='lower left', bbox_to_anchor=(.04, .095), frameon=False, labelcolor=MUTED, fontsize=11)
    fig.text(.045, .065, 'Labels: median speed + passed/runs. Flash: 3 sequential rounds (range shown); others: one request per task.',
             color=MUTED, fontsize=10)
    fig.text(.045, .035, 'Greedy, thinking off. Different outputs and runtimes: an experiment record, not a controlled model leaderboard.',
             color=MUTED, fontsize=10)
    save(fig, 'coding-speed-and-correctness')


def context_chart():
    rows = []
    for name, label, key in [
        ('Qwen38-benchmark-results.json', 'IQ4_XS + lookup\n31,916-token cold prompt', 'context'),
        ('QwenFlash-benchmark-results.json', 'Flash IQ2_XS\n31,916-token cold prompt', 'context'),
        ('Qwen38-Q3-85K-results.json', 'Q3_K_XL\n83,916-token cold prompt', 'context_checks'),
        ('Huihui-Qwen38-results.json', 'Huihui IQ3_S\n31,916-token cold prompt', 'context_checks'),
    ]:
        group = load(name)[key]
        target = max(r['target'] for r in group)
        pair = {r['phase']: r for r in group if r['target'] == target}
        rows.append((label, pair['cold']['wall_seconds'], pair['resumed']['wall_seconds']))
    fig, ax = plt.subplots(figsize=(14, 7.6))
    fig.subplots_adjust(left=.27, right=.91, top=.72, bottom=.19)
    heading(fig, 'The second question is a different wait',
            'Full HTTP response time · cold prompt versus cached follow-up · logarithmic seconds axis')
    for y, (_, cold, warm) in enumerate(rows):
        ax.barh(y-.15, cold, height=.23, color=BLUE)
        ax.barh(y+.15, warm, height=.23, color=TEAL)
        for value, offset, color in ((cold,-.15,BLUE),(warm,.15,TEAL)):
            ax.text(value*1.14, y+offset, f'{value:.2f} s', va='center', color=color, fontsize=11)
    ax.set_xscale('log'); ax.set_xlim(.1, 600)
    ax.set_xticks([.1, 1, 10, 100]); ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.set_xlabel('Seconds to complete the response  ·  lower is faster', labelpad=12)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=11)
    ax.invert_yaxis(); ax.tick_params(length=0, pad=10); ax.grid(axis='x', alpha=.5); ax.set_axisbelow(True)
    fig.legend(handles=[Patch(color=BLUE, label='Cold input'), Patch(color=TEAL, label='Cached follow-up')],
               loc='lower left', bbox_to_anchor=(.04,.09), frameon=False, ncol=2)
    fig.text(.045, .05, 'All eight retrieval requests passed. Q3 used a larger prompt; answers, cache formats, and engines also differ.', color=MUTED, fontsize=10)
    fig.text(.045, .02, 'One cold request + one follow-up per row. This measures response completion, not time to first token or agent reliability.', color=MUTED, fontsize=10)
    save(fig, 'context-cache-latency')


def lookup_chart():
    lookup = load('sweeps/qwen38-lookup-small-edit.json')
    dflash = load('sweeps/qwen38-dflash-small-edit.json')
    values = [dflash['timings']['predicted_per_second'], lookup['timings']['predicted_per_second']]
    elapsed = [(r['timings']['prompt_ms']+r['timings']['predicted_ms'])/1000 for r in (dflash,lookup)]
    fig, axes = plt.subplots(1,2,figsize=(14,7.1))
    fig.subplots_adjust(left=.21,right=.94,top=.71,bottom=.32,wspace=.4)
    heading(fig, 'Lookup shines when the answer is already there',
            'Same mostly-copy edit fixture · 743 prompt tokens → 703 output tokens · both exact-edit checks passed')
    for ax, nums, title, unit, limit in zip(axes,[values,elapsed],['Output generation','Prompt + generation'],
                                           ['Decode tokens/s  ·  higher is faster','Engine elapsed seconds  ·  lower is faster'],[800,7.6]):
        ax.barh([0,1],nums,color=[BLUE,TEAL],height=.42)
        for y,num in enumerate(nums): ax.text(num+limit*.025,y,f'{num:.1f}' if nums is values else f'{num:.2f} s',va='center',fontsize=14,weight='bold')
        ax.set_yticks([0,1],['DFlash2','MTP + lookup']);ax.invert_yaxis();ax.set_xlim(0,limit)
        ax.set_title(title,loc='left',fontsize=15,weight='bold',pad=20);ax.set_xlabel(unit,labelpad=12)
        ax.grid(axis='x',alpha=.5);ax.set_axisbelow(True);ax.tick_params(length=0,pad=10)
    fig.text(.045,.15,f'{values[1]/values[0]:.2f}× decode speed',color=TEAL,fontsize=20,weight='bold')
    fig.text(.50,.15,f'{(1-elapsed[1]/elapsed[0])*100:.0f}% lower engine time',color=TEAL,fontsize=20,weight='bold')
    fig.text(.045,.08,'IQ4_XS at 32K. Small synthetic fixture; not fresh-code speed and not sustained repository-agent throughput.',color=MUTED,fontsize=10)
    fig.text(.045,.045,'Elapsed = reported prompt_ms + predicted_ms; excludes HTTP overhead. Separate local runs, one saved sample per profile.',color=MUTED,fontsize=10)
    save(fig,'lookup-workload')


def mtp_chart():
    records = [load('sweeps/'+name) for name in
               ('qwen38-mtp0.json','qwen38-mtp1-fullgpu.json','qwen38-mtp3-fullgpu.json','qwen38-mtp5.json')]
    fig, ax = plt.subplots(figsize=(14,7.4))
    fig.subplots_adjust(left=.09,right=.92,top=.73,bottom=.25)
    heading(fig,'More draft tokens did not always help',
            'Exploratory IQ4_XS tuning runs · 256-token output cap · thinking off · decode tokens/s')
    for index,color,label in [(0,TEAL,'Code + explanation fixture'),(1,BLUE,'Prose fixture')]:
        values=[record[index]['timings']['predicted_per_second'] for record in records]
        ax.plot([0,1,3,5],values,color=color,linewidth=2.8,marker='o',markersize=8,label=label)
        for x,y in zip([0,1,3,5],values): ax.annotate(f'{y:.1f}',(x,y),xytext=(0,12 if index==0 else -22),textcoords='offset points',ha='center',color=color,fontsize=12)
    ax.set_ylim(0,140);ax.set_xlim(-.25,5.4);ax.set_xticks([0,1,3,5]);ax.set_xlabel('Maximum MTP draft tokens  ·  0 = disabled',labelpad=12)
    ax.set_ylabel('Decode tokens/s',labelpad=12);ax.grid(axis='y',alpha=.5);ax.tick_params(length=0,pad=9)
    fig.legend(loc='lower left',bbox_to_anchor=(.04,.13),frameon=False,ncol=2)
    fig.text(.045,.075,'One generation per point. Historical launch variations are incompletely recorded; this is not an isolated causal ablation.',color=MUTED,fontsize=10)
    fig.text(.045,.04,'Outputs are not functionally graded here. No error bars: no independent repetitions for these points are retained.',color=MUTED,fontsize=10)
    save(fig,'mtp-draft-sweep')


def update_html():
    """Embed vector figures so the companion HTML remains a single offline file."""
    figures = [
        ('coding-speed-and-correctness', 'Coding speed and correctness',
         'Hatched pink bars mark at least one failed check. Flash shows three-run medians and observed ranges; other profiles have one run per task.',
         'Qwen38-benchmark-results.json'),
        ('context-cache-latency', 'Cold input versus cached follow-up',
         'Complete HTTP response time on a logarithmic scale. Prompt lengths are labeled; Q3 uses a larger input. All eight shown retrieval checks passed.',
         'Qwen38-Q3-85K-results.json'),
        ('lookup-workload', 'Lookup on a mostly-copy edit',
         'The same small fixture passed both exact-edit checks. Decode speed and engine elapsed time use different units; neither measures sustained fresh-code throughput.',
         'sweeps/qwen38-lookup-small-edit.json'),
        ('mtp-draft-sweep', 'Exploratory MTP draft-depth sweep',
         'One ungraded generation per point. Historical launch variations mean this is not a controlled causal ablation.',
         'sweeps/qwen38-mtp3-fullgpu.json'),
    ]
    blocks = []
    for name, title, caption, source in figures:
        svg = (OUT / (name+'.svg')).read_text(encoding='utf-8')
        svg = svg[svg.index('<svg'):]
        # Each Matplotlib SVG reuses IDs such as figure_1; namespace embedded copies.
        for identifier in re.findall(r'\bid="([^"]+)"', svg):
            svg = svg.replace(f'id="{identifier}"', f'id="{name}-{identifier}"')
            svg = svg.replace(f'href="#{identifier}"', f'href="#{name}-{identifier}"')
            svg = svg.replace(f'url(#{identifier})', f'url(#{name}-{identifier})')
        svg = svg.replace('<svg ', '<svg role="img" aria-label="'+html.escape(title,quote=True)+'" ',1)
        blocks.append('<figure class="benchmark-figure"><div class="chart-scroll">'+svg+'</div><figcaption><strong>'+title+'</strong> — '+caption+'</figcaption><p class="chart-links"><a href="assets/'+name+'.png">PNG</a> · <a href="assets/'+name+'.svg">SVG</a> · <a href="../data/'+source+'">Source data</a></p></figure>')
    section = '<!-- BENCHMARK_CHARTS_START --><section id="charts"><div class="section-label">Visual benchmark report</div><h2>Measurements in pictures</h2><p>Figures are generated from the retained JSON. Speed and correctness remain separate. These configurations differ in model, precision, runtime, context, and sample count.</p><p>Scroll wide figures sideways on smaller screens, or open a full-resolution export. No external assets or scripts are needed to read this page.</p>'+''.join(blocks)+'</section><!-- BENCHMARK_CHARTS_END -->'
    path = ROOT / 'docs' / 'index.html'
    document = path.read_text(encoding='utf-8')
    if '<!-- BENCHMARK_CHARTS_START -->' in document:
        document = re.sub(r'<!-- BENCHMARK_CHARTS_START -->.*?<!-- BENCHMARK_CHARTS_END -->',lambda _:section,document,flags=re.S)
    else:
        document = document.replace('<main>', '<main>'+section, 1)
        document = document.replace('<nav aria-label="Documentation">','<nav aria-label="Documentation"><a href="#charts">Charts</a>',1)
    css = '/* BENCHMARK_CHART_CSS */.benchmark-figure{margin:30px 0 40px;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#10151c}.chart-scroll{overflow-x:auto}.chart-scroll svg{width:100%;height:auto;display:block}.benchmark-figure figcaption{padding:16px 20px 0;color:var(--muted);font-size:14px}.chart-links{padding:0 20px 12px;font-size:13px}@media(max-width:700px){.chart-scroll svg{min-width:960px}}@media print{.chart-scroll{overflow:visible}.chart-scroll svg{min-width:0}.benchmark-figure{break-inside:avoid}}/* END_BENCHMARK_CHART_CSS */'
    document = re.sub(r'/\* BENCHMARK_CHART_CSS \*/.*?/\* END_BENCHMARK_CHART_CSS \*/','',document,flags=re.S)
    document = document.replace('</style></head>',css+'</style></head>',1)
    path.write_text(document,encoding='utf-8')


if __name__ == '__main__':
    coding_chart()
    context_chart()
    lookup_chart()
    mtp_chart()
    update_html()
    print('Generated four SVG/PNG figures and updated the standalone HTML.')
