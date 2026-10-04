"""Final offline evidence, accounting, stop-rule, share-scope and HTML checks."""
from collections import Counter
from datetime import datetime,timezone
import ast
import json
import re
import zipfile
from bs4 import BeautifulSoup
from common_report import *


def main():
    data=read(ROOT/'records/report-data.json');review=read(ROOT/'records/review-audit-round3.json')
    auth=read(ROOT/'records/review-authorization.json');manifest=read(ROOT/'records/review-manifest-round3.json')
    assert auth['closed'] and auth['completed_unique_cases']==48
    assert read(OPT/'records/round-budget.json')['closed']
    assert len(data['rows'])==336 and len({(r['method'],r['index']) for r in data['rows']})==336
    assert set(r['index'] for r in data['rows'])==set(range(48,96))
    for relative,expected in read(ROOT/'records/analysis-source-hashes.json').items():assert sha(REPO/relative)==expected,relative
    for relative,expected in manifest['source_files'].items():assert sha(REPO/relative)==expected,relative
    assert sha(ROOT/'records/review-manifest-round3.json')==auth['manifest_sha256']
    assert sha(ROOT/'review_prompt.txt')==sha(OPT/'review_prompt.txt')==auth['prompt_sha256']
    terminals=[]
    for case in manifest['cases']:
        assert sha(ROOT/case['packet'])==case['packet_sha256']
        base=ROOT/'api/round3'/case['case_id'];first=read(base/'terminal.json')
        if first['http_status']==429:
            retry=base/'transport-retry-1';assert read(base/'request.json')==read(retry/'request.json')
            assert read(base/'started.json')['raw_request_sha256']==read(retry/'started.json')['raw_request_sha256']
            assert first['usage'] is None;terminal=read(retry/'terminal.json')
        else:terminal=first
        assert terminal['http_status']==200 and terminal['usage'] is not None
        terminals.append(terminal)
    attempts=[read(p) for p in (ROOT/'api/round3').rglob('terminal.json')]
    assert len(attempts)==67 and sum(a['http_status']==429 for a in attempts)==19
    assert sum(t['usage']['total_tokens'] for t in terminals)==review['costs']['total_tokens']==752953
    assert all(datetime.fromisoformat(a['finished_at_utc'])<=datetime.fromisoformat(auth['closed_at_utc']) for a in attempts)
    assert review['summary']['parsed']==38 and review['summary']['raw_seven_field_coverage']==48
    assert data['summary']['compact_r3']['scored46']['corresponding_source_exposed']==44
    assert Counter(r['rank'] for r in data['jaccard_source_ranks'])==Counter({1:46,3:2})
    assert all(r['dropped']==0 for r in data['jaccard_source_ranks'])
    for row in read(ROOT/'records/primary-adjudication-round3.json')['records']:
        for relative,expected in row['evidence_hashes'].items():assert sha(REPO/relative)==expected
    for path in ROOT.glob('*.py'):ast.parse(path.read_text(encoding='utf-8'))
    html=(ROOT/'report.html').read_text(encoding='utf-8');soup=BeautifulSoup(html,'html.parser')
    embedded=json.loads(soup.find('script',id='report-data').string)
    assert len(embedded['rows'])==336 and len(soup.select('#pair-table'))==1
    assert not soup.select('script[src],link[rel=stylesheet],img[src^="http"]')
    assert not re.search(r'<!-- [A-Z_0-9]+ -->',html)
    assert '\ufffd' not in html and 'reasoning_content' not in html
    browser=read(ROOT/'records/browser-check.json');assert browser['passed'] and browser['externalRequests']==0
    assert browser['html_sha256']==sha(ROOT/'report.html')
    # Scanner loads the existing credential for exact matching only. It makes no requests.
    import run_native
    eng,_=run_native.engine();key=eng.secret().encode();assert len(key)>10
    scan=[p for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.txt','.py','.mjs','.html','.md')]
    for path in scan:assert key not in path.read_bytes(),'Credential detected in '+path.name
    accepted=dict(passed=True,at_utc=datetime.now(timezone.utc).isoformat(),new_solver_tasks=0,new_review_cases=48,new_review_http_attempts=67,
        new_review_tokens_known=752953,unknown_review_usage_attempts=19,old_solver_study_closed=True,supplemental_review_closed=True,
        initial240_plus_new48_semantic_scope=288,main_solver_executions=336,distinct_complex_tasks=48,
        source_hashes_verified=len(read(ROOT/'records/analysis-source-hashes.json')),same_review_prompt=True,
        source_only_memory_unchanged=True,full_seven_field_raw_coverage_round3=48,raw_json_parseable_round3=38,
        strict_schema_quote_pass_round3=5,existing_claims_all_citations_locatable_round3=28,
        r3_source_exposure_corrected_from_private_ranges=44,known_input_caveat_disclosed=True,
        primary_ai_adjudication_targets=12,human_ground_truth_claimed=False,
        browser_verified=True,credential_scan_files=len(scan),credential_scan='Exact current GLM credential not found',
        rendering='Standalone responsive offline HTML; tables and evidence remain accessible without JS',money=None)
    save(ROOT/'records/report-acceptance.json',accepted)
    share_root=ROOT/'share';share_root.mkdir(exist_ok=True)
    mapping={'report.html':ROOT/'report.html','report-complete.md':ROOT/'report-complete.md','review_prompt.txt':ROOT/'review_prompt.txt','sources.json':ROOT/'sources.json',
        'evidence/report-data.json':ROOT/'records/report-data.json','evidence/review-audit-round3.json':ROOT/'records/review-audit-round3.json',
        'evidence/primary-adjudication-round3.json':ROOT/'records/primary-adjudication-round3.json','evidence/report-acceptance.json':ROOT/'records/report-acceptance.json',
        'evidence/five-methods-review-audit.json':OPT/'records/review-audit-initial.json','evidence/five-methods-raw-field-extraction.json':OPT/'records/raw-field-extraction.json'}
    readme='打开 report.html 即可离线阅读完整报告。页面不调用模型、不连接网络。\nreport-complete.md为完整文字副本；evidence包含统计及引用审核，不包含模型内部推理。\n原始求解归档另在研究仓库保留。本包没有凭据、缓存、workspace或个人资料。\n数据许可与证据限制见正文。\n'
    (share_root/'README.txt').write_text(readme,encoding='utf-8')
    members=[]
    for relative,source in mapping.items():
        target=share_root/relative;target.parent.mkdir(parents=True,exist_ok=True);payload=source.read_bytes()
        assert key not in payload and b'"reasoning_content"' not in payload
        target.write_bytes(payload);members.append(dict(path=relative,bytes=len(payload),sha256=sha(target)))
    members.append(dict(path='README.txt',bytes=(share_root/'README.txt').stat().st_size,sha256=sha(share_root/'README.txt')))
    bundle=ROOT/'jaccard-memory-report.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as out:
        for item in members:out.write(share_root/item['path'],arcname=item['path'])
    with zipfile.ZipFile(bundle) as archived:
        assert set(archived.namelist())=={m['path'] for m in members}
        for item in members:
            import hashlib
            assert hashlib.sha256(archived.read(item['path'])).hexdigest()==item['sha256']
    save(ROOT/'records/share-manifest.json',dict(files=len(members),members=members,zip_sha256=sha(bundle),zip_bytes=bundle.stat().st_size,
        excludes=['credentials','api raw responses including reasoning','workspaces','caches','unrelated personal material'],exact_credential_scan='passed',members_hash_verified=True))
    print(json.dumps(dict(passed=True,html_bytes=(ROOT/'report.html').stat().st_size,share_files=len(members),zip_bytes=bundle.stat().st_size,new_solver_tasks=0,new_review_tokens=752953),ensure_ascii=False))


if __name__=='__main__':main()
