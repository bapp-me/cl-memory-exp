"""Standalone scientific figure from verified D0 tables (no semantic labels)."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import *


def main():
    data=read(ROOT/'records/d0-summary.json');pairs=read(ROOT/'records/efficiency-pairs.json')
    full={x['method']:x for x in data['summaries'] if x['benchmark']=='codeeval' and x['scope']=='all_executed'}
    target={x['method']:x for x in data['summaries'] if x['benchmark']=='codeeval' and x['scope']=='effective_complex'}
    paired={x['method']:x for x in pairs if x['benchmark']=='codeeval'}
    names=['No Memory*','Bounded ICL','Jaccard episodic*','Mem0','AWM','ACE (subtotal)']
    colors=['#6b7280','#1d4ed8','#059669','#d97706','#7c3aed','#dc2626']
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,3,figsize=(15,5.7),gridspec_kw={'width_ratios':[1.15,1,1.05]})
    ax=axs[0]
    for i,m in enumerate(METHODS):
        x=full[m]['known_usage_subtotal']['totalTokens']/1e6;y=target[m]['correct']/46*100
        ax.scatter(x,y,s=90,color=colors[i]);ax.annotate(names[i],(x,y),xytext=(5,9 if m!='mem0' else -17),textcoords='offset points',fontsize=9)
    ax.set_xscale('log');ax.set_xlim(.23,12);ax.set_ylim(33,64);ax.set_xlabel('All 96 code tasks: known tokens (million, log)');ax.set_ylabel('Complex targets correct / 46 (%)');ax.set_title('Quality and full-stream cost');ax.grid(alpha=.15)
    ys=range(6);ax=axs[1]
    gains=[paired[m]['improvement_candidates'] for m in METHODS];harms=[-paired[m]['harm_candidates'] for m in METHODS]
    ax.barh(ys,gains,color='#10b981',label='No Memory fail -> method pass');ax.barh(ys,harms,color='#f97316',label='No Memory pass -> method fail')
    ax.set_yticks(list(ys),names);ax.invert_yaxis();ax.axvline(0,color='#475569',lw=.8);ax.set_xlim(-5,10);ax.set_xlabel('Paired target count / 46');ax.set_title('Observed differences, not causal effects');ax.legend(fontsize=7.5,loc='upper center',bbox_to_anchor=(.5,-.16))
    ax=axs[2];cov={x['method']:x for x in data['source_coverage']}
    ax.barh([y-.18 for y in ys],[cov[m]['source_selected_before_packing'] for m in METHODS],height=.34,color='#93c5fd',label='Source provenance selected')
    ax.barh([y+.18 for y in ys],[cov[m]['source_provenance_injected'] for m in METHODS],height=.34,color='#2563eb',label='Source provenance injected')
    ax.set_yticks(list(ys),names);ax.invert_yaxis();ax.set_xlim(0,50);ax.set_xlabel('Source-target pairs / 46');ax.set_title('Provenance is not semantic fidelity');ax.legend(fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.16))
    fig.suptitle('Section 7.2: six baseline methods, R=1',fontsize=15,y=1.01)
    fig.text(.01,-.015,'* Historical descriptive reuse; aliases and old usage have limits. ACE has missing HTTP usage. Fixed scoring mask retained, including flagged test shadowing.\nTokens include cache and auxiliary roles; no dollar-cost or causal-efficiency claim. Source: records/d0-summary.json and efficiency-pairs.json.',fontsize=8,color='#475569')
    fig.tight_layout();(ROOT/'figures').mkdir(exist_ok=True)
    fig.savefig(ROOT/'figures/baseline-analysis.png',dpi=180,bbox_inches='tight');fig.savefig(ROOT/'figures/baseline-analysis.svg',bbox_inches='tight')
    svg=ROOT/'figures/baseline-analysis.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


if __name__=='__main__':main()
