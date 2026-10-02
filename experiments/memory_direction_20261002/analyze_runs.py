"""Deterministic pilot scoring and transparent usage accounting."""
from __future__ import annotations
import json
import gzip
import re
import sqlite3
from pathlib import Path
from lab_common import ROOT, save_json


def extract_answer(text):
    decoder=json.JSONDecoder()
    for match in re.finditer(r'\{',text):
        try:
            obj,_=decoder.raw_decode(text[match.start():])
            if isinstance(obj,dict) and 'answer' in obj:return obj
        except ValueError:pass
    return None


def numeric_answer(value):
    if isinstance(value,(int,float)) and not isinstance(value,bool):return float(value)
    if isinstance(value,dict):
        for key in ('answer','median_price_usd','average_listed_price_usd','value','result','percentage','count'):
            if key in value:return numeric_answer(value[key])
        return None
    if isinstance(value,str):
        cleaned=value.replace(',','')
        money=re.search(r'\$\s*(-?\d+(?:\.\d+)?)',cleaned)
        if money:return float(money.group(1))
        numbers=re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])',cleaned)
        if len(numbers)==1:return float(numbers[0])
    return None


def main():
    questions={q['question_id']:q for q in json.loads((ROOT/'.cache/clbench/questions.json').read_text(encoding='utf-8'))}
    con=sqlite3.connect((ROOT/'.cache/clbench/products.db').resolve().as_uri()+'?mode=ro',uri=True)
    con.execute('PRAGMA query_only=ON')
    rows=[]
    for directory in sorted((ROOT/'results/runs').iterdir()):
        if not (directory/'summary.json').exists():continue
        inp=json.loads((directory/'input.json').read_text(encoding='utf-8'))
        summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
        result=summary.get('result',{});hermes=inp.get('agent','').startswith('Hermes')
        text=result.get('final_response','') if hermes else result.get('result','')
        obj=extract_answer(text)
        sqlpath=directory/'sql.jsonl'
        sqlrows=[json.loads(x) for x in sqlpath.read_text(encoding='utf-8').splitlines()] if sqlpath.exists() else []
        usage=result.get('usage',{}) if not hermes else {'input_tokens':result.get('input_tokens',0),'cache_read_input_tokens':result.get('cache_read_tokens',0),'output_tokens':result.get('output_tokens',0)}
        miss=usage.get('input_tokens',0);cached=usage.get('cache_read_input_tokens',0)
        output=usage.get('output_tokens',0)
        native_usage={'input_uncached':miss,'input_cached':cached,'output_tokens':output}
        ledger_path=directory/'http/ledger.jsonl'
        usage_source='native final object'
        incomplete_usage=0
        if ledger_path.exists():
            miss=cached=output=0;usage_source='all recorded HTTP requests'
            for line in ledger_path.read_text(encoding='utf-8').splitlines():
                entry=json.loads(line)
                if entry.get('status')!=200:continue
                merged={}
                for u in entry.get('usage_events',[]):merged.update(u)
                miss+=merged.get('input_tokens',0);cached+=merged.get('cache_read_input_tokens',0);output+=merged.get('output_tokens',0)
                incomplete_usage+=int(len(entry.get('usage_events',[]))<2)
        price_peak=(miss*.3+cached*.006+output*1.2)/1_000_000 if inp['provider']=='deepseek' else None
        benchmark=directory.name.startswith(('v1-','v2-','h1-')) and 'smoke' not in directory.name and not inp.get('capture_only')
        answer=None;correct=None;computed=None;official_correct=None
        if benchmark and obj:
            answer=numeric_answer(obj['answer'])
            gold=questions[inp['question_id']]['answer']
            if questions[inp['question_id']]['answer_type']=='integer':
                correct=answer==gold
                official_correct=correct
            else:
                correct=abs(answer-float(gold))<.005 if isinstance(answer,(float,int)) and isinstance(gold,(float,int)) else answer==gold
                official_correct=abs(answer-float(gold))<=max(float(questions[inp['question_id']].get('tolerance',0)),abs(float(gold))*.01) if isinstance(answer,(float,int)) and isinstance(gold,(float,int)) else answer==gold
            if isinstance(obj.get('sql'),str):
                try:
                    cursor=con.execute(obj['sql'])
                    computed={'columns':[c[0] for c in cursor.description], 'first_row':cursor.fetchone()}
                except sqlite3.Error as exc:computed={'error':str(exc)}
        events=[]
        events_path=directory/'events.jsonl'
        for line in events_path.read_text(encoding='utf-8').splitlines() if events_path.exists() else []:
            try:events.append(json.loads(line))
            except ValueError:pass
        calls=[]
        for event in events:
            for part in event.get('message',{}).get('content',[]) if isinstance(event.get('message',{}).get('content',[]),list) else []:
                if isinstance(part,dict) and part.get('type')=='tool_use':calls.append({'name':part.get('name'),'input':part.get('input')})
        if hermes:
            for msg in result.get('messages',[]):
                for call in msg.get('tool_calls',[]) or []:
                    fn=call.get('function',{})
                    calls.append({'name':fn.get('name'),'input':fn.get('arguments')})
        memory_reads=[x for x in calls if x['name'] in ('Read','Grep','Glob') and 'memory' in json.dumps(x['input']).lower()]
        initial=sorted((directory/'http').glob('*-request.json*'))
        request_path=(initial[0].with_suffix('') if initial and initial[0].suffix=='.gz' else initial[0]) if initial else directory/'http/001-request.json'
        request_text=request_path.read_text(encoding='utf-8') if request_path.exists() else gzip.decompress(request_path.with_suffix('.json.gz').read_bytes()).decode() if request_path.with_suffix('.json.gz').exists() else ''
        seeded=bool(inp.get('memory_from') or inp.get('memory_seed'))
        seed_path=directory/'memory_before'
        if not (seed_path/'MEMORY.md').exists() and inp.get('memory_from'):
            seed_path=ROOT/'results/runs'/inp['memory_from']/'memory_after'
        if not (seed_path/'MEMORY.md').exists() and inp.get('memory_seed'):
            seed_path=Path(inp['memory_seed'])
            if not seed_path.is_absolute():seed_path=ROOT/seed_path
        index_lines=(seed_path/'MEMORY.md').read_text(encoding='utf-8').splitlines() if (seed_path/'MEMORY.md').exists() else []
        markers=[json.dumps(line.strip(),ensure_ascii=False)[1:-1] for line in index_lines if ('environment.md' in line or (hermes and len(line)>20))]
        index_present=bool(seeded and markers and any(marker in request_text for marker in markers))
        consumption_label={'none':'no cross-task memory','native':'optional file reads; native auto-memory not observed','inject':'directly supplied experience'}[inp['mode']]
        if inp['mode']=='native' and inp.get('full_native'):
            consumption_label='normal native entry; memory index in initial context' if index_present else 'normal native entry; inspect initial context for memory indexing'
        if hermes and inp['mode']=='native':consumption_label='native curated memory loaded into initial context' if index_present else 'native memory; initial context needs inspection'
        rows.append({'run_id':directory.name,'protocol':inp.get('protocol','debug-v0'),
                     'eligible_for_main_comparison':benchmark,'provider':inp['provider'],
                     'question_id':inp['question_id'],'mode':inp['mode'],'write_memory':inp['write_memory'],
                     'consumption_label':consumption_label,'initial_memory_index_observed':index_present,
                     'agent':inp.get('agent'),'completed':bool(result.get('completed')) if hermes else not result.get('is_error',True),'answer':answer,'raw_answer':obj.get('answer') if obj else None,'correct':correct,
                     'official_numeric_tolerance_correct':official_correct,
                     'submitted_sql_value':computed,'sql_queries':len(sqlrows),
                     'sql_errors':sum('error' in x['result'] for x in sqlrows),
                     'seconds':summary['seconds'],'input_uncached':miss,'input_cached':cached,'output_tokens':output,
                     'usage_source':usage_source,'incomplete_usage_requests':incomplete_usage,'native_final_usage_for_audit':native_usage,
                     'deepseek_cost_usd_range':([round(price_peak/2,6),round(price_peak,6)] if price_peak is not None else None),
                     'reported_native_cost_usd_not_actual':result.get('total_cost_usd'),
                     'memory_reads':memory_reads,'memory_files':summary['memory_files']})
    con.close()
    record={'runs':rows,'pricing_note':'DeepSeek official 2026-10-02 peak USD/M: input miss .30, hit .006, output 1.20; off-peak half. Range is estimate, not account invoice. GLM price not yet verified, report tokens only.',
            'limits':['Single repetitions are screening only.','Protocol v0/debug runs excluded from main memory effect comparisons.',
                      'Timing is observed wall time and includes local tool/runtime overhead.']}
    save_json(ROOT/'results/run-scoreboard.json',record)
    for row in rows:
        if row['eligible_for_main_comparison']:
            print(json.dumps({k:row[k] for k in ['run_id','correct','answer','sql_queries','sql_errors','seconds','deepseek_cost_usd_range']},ensure_ascii=True))


if __name__=='__main__':main()
