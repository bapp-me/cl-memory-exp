"""Export descriptive memory payload trajectories, no model calls."""
import os
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.local/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    rows=json.loads((ROOT/'records/full-mechanical-task-metrics.json').read_text(encoding='utf8'))
    names={'pi_none':'No Memory','pi_notepad':'Notepad','pi_jaccard':'Jaccard',
           'claude_memory_ready':'Claude Code','codex_memory_ready':'Codex','hermes_memory_ready':'Hermes'}
    colors=['#738397','#17817a','#cb7640','#8769ac','#3477b0','#ad6580']
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
                         'axes.spines.right':False,'svg.fonttype':'none','svg.hashsalt':'clbench-full-analysis'})
    fig,axes=plt.subplots(1,2,figsize=(14,5.8))
    for ax,env,title in zip(axes,['database_exploration','codebase_adaptation'],['Database','Codebase']):
        for (method,label),color in zip(names.items(),colors):
            selected=sorted([r for r in rows if r['method']==method and r['environment']==env],key=lambda r:r['index'])
            ax.plot([r['index']+1 for r in selected],[r['before']['physical_bytes'] for r in selected],
                    marker='o',markersize=3,linewidth=1.8,label=label,color=color)
        ax.set_yscale('symlog',linthresh=100);ax.set_xlabel('Task position');ax.set_title(title,fontweight='bold')
        ax.grid(alpha=.16);ax.set_axisbelow(True)
        ax.axvline(20.5 if title=='Database' else 9.5,color='#777777',linestyle=':',alpha=.7)
    axes[0].set_ylabel('Recorded pre-task memory payload (bytes; symlog)')
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,ncol=6,loc='upper center',bbox_to_anchor=(.5,.91),frameon=False)
    fig.suptitle('CL-Bench | Memory payload carried across tasks | R=1',fontsize=16,y=.99)
    fig.text(.055,.025,'Native: memory-file payload. Pi: canonicalized persisted-state payload; feedback stored separately.\n'
             'Different representations, not a storage-efficiency ranking. Dotted lines mark database migration / repository switch.\n'
             'File presence does not establish model visibility or causal benefit. Hermes Codebase includes one unscored interrupted task.',fontsize=10)
    fig.tight_layout(rect=(.02,.16,.99,.85))
    target=ROOT/'figures';target.mkdir(exist_ok=True)
    for ext in ['png','svg']:fig.savefig(target/f'full-memory-payload.{ext}',dpi=180,bbox_inches='tight')
    print('Saved full-memory-payload.png and .svg')


if __name__=='__main__':main()
