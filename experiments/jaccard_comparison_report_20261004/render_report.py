"""Create a self-contained, offline HTML report and a complete Markdown companion."""
from pathlib import Path
from html import escape
import json
import re
import statistics
import markdown
from common_report import *

def number(value):return '未知/不适用' if value is None else f'{value:,}' if isinstance(value,int) else f'{value:,.2f}'
def table(headers,rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def details(label,body):return '<details><summary>'+escape(label)+'</summary>'+body+'</details>'
def pre(value):return '<pre><code>'+escape(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2))+'</code></pre>'
def case_html(example,names):
    content=details('基础题原文 · 来源 s'+str(example['source_index']).zfill(3),pre(example['source_prompt']))
    content+=details('复杂题原文 · '+example['task_id'],pre(example['target_prompt']))
    for run in example['runs']:
        calls=[]
        for message in run['trajectory']:
            if message['role']=='assistant':
                for block in message.get('content',[]):
                    if block.get('type')=='toolCall':calls.append((block['name'],block.get('arguments',{})))
        route=' → '.join(c[0].removeprefix('MEMORY_') for c in calls)
        body='<p class="trace-route">'+escape(route)+'</p>'
        body+=details('逐步工具请求（原参数，未执行）',''.join('<h5>'+escape(str(i+1)+'. '+name)+'</h5>'+pre(args) for i,(name,args) in enumerate(calls)))
        body+=details('实际工具输出与公开消息',pre(run['trajectory']))
        body+=details('最终提交代码',pre(run['submission'] or '没有提交'))
        body+=details('提交后评分日志（模型做题时不可见）',pre(run['evaluation']))
        status='通过' if run['correct'] else '未通过'
        content+=details(f"{names[run['method']]} · {status} · {run['tokens']:,} tokens · Python {run['python_calls']} / 记忆 {run['memory_calls']}",body)
    return '<div class="case-box">'+content+'</div>'

def main():
    data=read(ROOT/'records/report-data.json');names=data['names'];summary=data['summary']
    initial=read(OPT/'records/review-audit-initial.json')
    r3=read(ROOT/'records/review-audit-round3.json') if (ROOT/'records/review-audit-round3.json').exists() else None
    complete=bool(r3 and r3['costs']['model_responses']==48)
    sources=read(ROOT/'sources.json')
    replacements={}
    replacements['DATASET_TABLE']=table(['项目','实际内容'],[
        ['文件/版本',data['dataset']['file']+' / '+data['dataset']['revision']],['文件SHA-256',data['dataset']['file_sha256']],
        ['基础题/复杂题','48 / 48；原文件前48条为raw、后48条为new'],['基础历史通过','42/47可评分；另5失败、1资产不可评分仍留库'],
        ['主体比较','7配置 × 48目标 = 336次既有执行；不同目标只有48个'],['记忆库大小',number(data['dataset']['library_bytes'])+'序列化bytes；48条历史 / 279事件 / 98文件']])
    replacements['MAIN_TABLE']=table(['配置','正确/46','计分题tokens','全48题tokens','Python/46','记忆调用/46','模型调用/46'],[
        [names[m],str(v['scored46']['correct'])+'/46',number(v['scored46']['tokens']),number(v['all48']['tokens']),v['scored46']['python_calls'],v['scored46']['memory_calls'],v['scored46']['model_calls']] for m,v in summary.items()])
    replacements['PAIRED_TABLE']=table(['相对Jaccard','成功增益/损失','总tokens变化','用量倍数','更省tokens题数/46','逐题差值中位数'],[
        [names[m],f"{len(v['paired']['gains'])} / {len(v['paired']['losses'])}",f"+{v['paired']['token_delta']:,}",f"{v['paired']['token_ratio']:.2f}×",v['paired']['lower_token_tasks'],number(v['paired']['median_token_delta'])] for m,v in summary.items() if m!='jaccard'])
    replacements['COST_COMPONENT_TABLE']=table(['配置（46题）','非缓存输入','缓存读取','输出含推理','合计'],[
        [names[m],number(v['scored46']['input_tokens']),number(v['scored46']['cache_tokens']),number(v['scored46']['output_tokens']),number(v['scored46']['tokens'])] for m,v in summary.items()])
    replacements['OBSERVABILITY_TABLE']=table(['配置（46题）','对应来源曝光','截断调用','空搜索','非正文占比','静态累计bytes','动态累计bytes','错误观察'],[
        [names[m],number(v['scored46']['corresponding_source_exposed']),v['scored46']['truncated_calls'],number(v['scored46']['empty_search_calls']),
         '不适用' if v['scored46']['noncontent_fraction'] is None else f"{v['scored46']['noncontent_fraction']:.1%}",number(v['scored46']['static_exposure_bytes']),number(v['scored46']['dynamic_exposure_bytes']),v['scored46']['error_observations']] for m,v in summary.items()])
    opt=[read(OPT/'rounds'/rid/'analysis.json') for rid in ('r1','r2','r3')]
    replacements['OPTIMIZATION_TABLE']=table(['轮次','主要改动','正确/46','计分tokens','Python','记忆调用','旧预登记门槛'],[
        [a['round_id'],['精简公共响应','改为按需索引','独立复验第1轮'][i],a['summaries']['scored46']['candidate']['correct'],number(a['summaries']['scored46']['candidate']['tokens']),
         a['summaries']['scored46']['candidate']['python_calls'],a['summaries']['scored46']['candidate']['memory_calls'],'通过' if all(a['checks'].values()) else '未通过效率门槛'] for i,a in enumerate(opt)])
    replacements['DIAGNOSTIC_TABLE']=table(['配置','主口径/46','排除316 /45','再排除954 /44'],[
        [names[m],v['scored46']['correct'],v['diagnostic45']['correct'],v['diagnostic44']['correct']] for m,v in summary.items()])
    for example in data['examples']:replacements['CASE_'+example['task_id'].split('/')[-1]]=case_html(example,names)
    replacements['REVIEW_PROMPT']=details('完整实际评审提示词（与前五方案字节相同）',pre((ROOT/'review_prompt.txt').read_text(encoding='utf-8')))
    example_case='report-r3-051'
    folder=ROOT/'api/round3'/example_case
    if (folder/'visible-output.txt').exists():
        packet=read(ROOT/'packets/round3'/f'{example_case}.json')
        from review_glm import render
        replacements['REVIEW_EXAMPLE']=('<div class="case-box"><p>真实评审示例：'+example_case+'。展示完整输入与模型公开输出；下方“有效”只指结构/引用检查，不保证语义解释成立。</p>'+
            details('实际API请求参数（无认证头）',pre({k:v for k,v in read(folder/'request.json').items() if k!='messages'}))+
            details('完整用户输入：带区段名和行号的证据包',pre(render(packet)))+
            details('完整模型公开输出（不含内部推理）',pre((folder/'visible-output.txt').read_text(encoding='utf-8')))+
            details('请求终态与校验错误',pre(read(folder/'terminal.json')))+ '</div>')
    else:replacements['REVIEW_EXAMPLE']='<p>补充审查尚在进行，终稿将填入真实示例。</p>'
    reviewrows=[]
    for m in METHODS:
        s=initial['summary'][m];reviewrows.append([names[m],'48/48',s['parsed'],s['strict_valid'],s['fully_citation_grounded']])
    if r3:
        s=r3['summary'];reviewrows.append([names['compact_r3'],str(r3['costs']['model_responses'])+'/48',s['parsed'],s['strict_valid'],s['fully_citation_grounded']])
    replacements['REVIEW_QUALITY_TABLE']=table(['配置','模型回复/应审','JSON可解析','严格结构/原引文通过','已有判断引用全可定位'],reviewrows)
    if r3:
        replacements['REVIEW_QUALITY_TABLE']+=f"<p>第三轮原四项字段可逐字提取{s['raw_four_field_coverage']}/48，七项齐全{s['raw_seven_field_coverage']}/48；{48-s['parsed']}条JSON不合格。初始五方案的64/240严格通过、163/240已有判断引用可定位，与第三轮使用相同校验函数。所有比例均不称语义准确率。</p>"
    replacements['REVIEW_LABEL_TABLE']=table(['合法且引文可定位的标签次数']+[names[m] for m in METHODS]+['第3轮'],[
        [tag]+[initial['summary'][m]['grounded_label_counts'].get(tag,0) for m in METHODS]+[r3['summary']['grounded_label_counts'].get(tag,0) if r3 else '待完成'] for tag in TAGS])
    raw_initial=read(OPT/'records/raw-field-extraction.json')['raw_scalar_distributions']['initial']
    fieldnames={'source_quality':'来源质量','memory_fidelity':'表示保真','target_applicability':'目标适用性','visible_use':'可见使用',
        'search_strategy':'搜索策略','failure_boundary':'失败边界','reading_efficiency':'读取效率'}
    dist=[]
    for field,label in fieldnames.items():
        rows=[[names[m],'；'.join(k+': '+str(v) for k,v in raw_initial[m][field].items())] for m in METHODS]
        if r3:rows.append([names['compact_r3'],'；'.join(k+': '+str(v) for k,v in r3['summary']['raw_scalar_distributions'][field].items())])
        dist.append(details(label+' · '+field+' · 原文值完整分布（含坏JSON；不是核验通过的事实标签）',table(['配置，每行分母48','模型原文值及次数'],rows)))
    replacements['SEMANTIC_DISTRIBUTIONS']=''.join(dist)
    adjudication_path=ROOT/'records/primary-adjudication-round3.json'
    replacements['ADJUDICATION_TABLE']=table(['第三轮目标','复核说明（AI证据检查，非人工真值）'],[[r['task_id'],r['note']] for r in read(adjudication_path)['records']]) if adjudication_path.exists() else '<p>重点复核尚在进行。</p>'
    oldcost=read(OPT/'records/completion-audit.json')
    maincost=sum(v['all48']['tokens'] for v in summary.values())
    r3cost=r3['costs'] if r3 else {}
    replacements['COST_LEDGER']=table(['范围','次数/覆盖','已知tokens','未知usage尝试','说明'],[
        ['本报告主体求解','336次',number(maincost),0,'Jaccard48＋五版240＋第三轮48'],
        ['三轮优化历程','144次',number(oldcost['known_solver_tokens']),0,'第三轮已在上一行；两行不可相加'],
        ['初始五方案语义审查','240模型回复 / 245 HTTP',number(initial['costs']['total_tokens']),5,'此前5次429保留'],
        ['原第1/2轮跟进审查','24模型回复 / 24 HTTP','393,024',0,'抽样，不属于288条主语义比较'],
        ['本报告新增第三轮审查',f"{r3cost.get('model_responses',0)}模型回复 / {r3cost.get('http_attempts',0)} HTTP",number(r3cost.get('total_tokens')),r3cost.get('unknown_usage_attempts','待完成'),'仅分析旧轨迹，非新增求解'],
        ['基础历史构建','已有48源任务','137,698','历史口径','复用不重复支付'],['金额','全部范围','未知','—','无已核验价格/账单']])
    replacements['REFERENCES']='<ol>'+''.join('<li><a href="'+escape(s['url'],quote=True)+'" target="_blank" rel="noopener">'+escape(s['title'])+'</a> — '+escape(s['type'])+'。'+escape(s['use'])+'</li>' for s in sources)+'</ol>'
    replacements['REPRODUCTION']=('<p>报告数据的本地复核：从仓库根目录运行以下命令，仅读取已有记录，不调用模型或执行题目。新checkout应先按原始归档说明恢复运行证据与固定数据资产。</p>'+pre(
        'python -X utf8 experiments/jaccard_comparison_report_20261004/build_data.py\npython -X utf8 experiments/jaccard_comparison_report_20261004/audit_semantics.py\npython -X utf8 experiments/jaccard_comparison_report_20261004/render_report.py')+
        '<p>主要证据：report-data.json（336逐题记录与统一表）、analysis-source-hashes.json（原记录哈希）、review_prompt.txt（完整提示词）、review-audit-round3.json（逐字段与引用）、sources.json（文献）、report-acceptance.json（最终核验）。完整原始求解日志另在原五模式与三轮优化归档中保留。分享包的阅读不依赖这些原始目录。</p>')
    replacements['INTERACTIVE_OVERVIEW']='''<section class="interactive" aria-label="交互质量与成本比较"><h3>同一批任务，质量与成本落在哪里？</h3><div class="controls"><label>统计口径 <select id="overview-scope"><option value="scored46">主口径：46题</option><option value="all48">全部48次执行成本</option><option value="diagnostic45">诊断：排除316，45题</option><option value="diagnostic44">诊断：再排除954，44题</option></select></label><label>突出配置 <select id="overview-method"></select></label></div><div id="quality-chart" class="chart"></div><p id="overview-detail" class="selection-detail" aria-live="polite"></p><h4>用量构成：缓存仍是token，但不等于同价支出</h4><div class="legend"><span class="legend-input">非缓存输入</span><span class="legend-cache">缓存读取</span><span class="legend-output">输出（含推理）</span></div><div id="cost-bars"></div><p class="caption">蓝色点为Jaccard，绿色点为第3轮，其余为灰色；使用选择框查看配置数值。图中的点是单批观测，没有统计置信区间；全部48口径仍只有46题可评分。向左代表少tokens，向上代表更多成功。</p></section>'''
    replacements['INTERACTIVE_TASKS']='''<section class="interactive" aria-label="逐题配对"><h3>逐题看：哪些成功变化，哪些花费变化？</h3><div class="controls"><label>比较配置 <select id="pair-method"></select></label><label>结果筛选 <select id="pair-filter"><option value="all">所有48题</option><option value="gain">新增成功</option><option value="loss">成功损失</option><option value="both_success">两边均成功</option><option value="both_failure">两边均失败</option><option value="unscorable">不计分</option></select></label></div><p id="pair-summary" aria-live="polite"></p><div class="table-wrap"><table id="pair-table"><thead><tr><th>题目</th><th>Jaccard</th><th>候选</th><th>tokens差值</th><th>Python差值</th><th>记忆调用</th><th>对应源曝光</th></tr></thead><tbody></tbody></table></div><p class="caption">tokens差值＝候选−Jaccard；负数代表更省。这里不把“更省但答错”自动视为改进，也不把两个失败当作质量等价。</p></section>'''
    replacements['METHOD_FLOW']='''<div class="flow-compare"><div><strong>自动预取</strong><ol><li>题面与48条历史做本地词匹配</li><li>前三条完整历史进入首次请求</li><li>模型直接执行、检查、提交</li></ol></div><div><strong>自主访问</strong><ol><li>题面与工具说明／索引进入首次请求</li><li>模型选查询或文件，工具返回片段</li><li>模型决定补读、改查或停止</li><li>模型执行、检查、提交</li></ol></div></div>'''
    text=(ROOT/'report.md').read_text(encoding='utf-8')
    for key,value in replacements.items():text=text.replace('<!-- '+key+' -->',value)
    assert not re.search(r'<!-- [A-Z_0-9]+ -->',text)
    (ROOT/'report-complete.md').write_text(text,encoding='utf-8')
    body=markdown.markdown(text,extensions=['tables','fenced_code','toc'],extension_configs={'toc':{'permalink':False}})
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(body,'html.parser')
    for grid in soup.find_all('table'):
        if not (grid.parent.name=='div' and 'table-wrap' in grid.parent.get('class',[])):
            wrapper=soup.new_tag('div');wrapper['class']='table-wrap';grid.wrap(wrapper)
    body=str(soup)
    # Markdown's generic generated Unicode IDs work in every local browser.
    headings=re.findall(r'<h2 id="([^"]+)">(.*?)</h2>',body)
    nav=''.join('<a href="#'+escape(key)+'">'+re.sub('<[^>]+>','',title)+'</a>' for key,title in headings)
    embedded=json.dumps(dict(names=names,summary=summary,rows=[{k:v for k,v in r.items() if k not in ('queries','source_path','recovery_proxy')} for r in data['rows']]),ensure_ascii=False).replace('<','\\u003c')
    template=(ROOT/'template.html').read_text(encoding='utf-8')
    html=template.replace('%%BODY%%',body).replace('%%NAV%%',nav).replace('%%DATA%%',embedded).replace('%%STATUS%%','已完成 · 独立离线报告' if complete else '草稿 · 补充审查进行中')
    # Keep source trailing whitespace visible/copyable without Git whitespace defects.
    def encode_pre(match):
        content=re.sub(r'[ \t]+(?=\r?$)',lambda m:''.join('&#9;' if c=='\t' else '&#32;' for c in m.group()),match.group(1),flags=re.M)
        return '<pre><code>'+content+'</code></pre>'
    html=re.sub(r'<pre><code>(.*?)</code></pre>',encode_pre,html,flags=re.S)
    (ROOT/'report.html').write_text(html,encoding='utf-8')
    print(json.dumps(dict(complete=complete,html_bytes=len(html.encode()),sections=len(headings),tokens_main336=maincost),ensure_ascii=False))

if __name__=='__main__':main()
