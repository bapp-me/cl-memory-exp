"""Explicit local syntax-only repairs after inspecting full visible output.

No API retry, no invented completion, and originals are never overwritten.
"""
from common import *
from review import validate

PATCHES=[
 ('formal','deepseek','c-27a382753b32',',"labels":[','},"labels":[','Insert missing semantic-object closing brace before labels; no content change.'),
 ('pilot2_glm_high','glm','c-af1fad3cc92b','        "note": "injected_ids 列表包含 sai-00079 与 sai-00080（injected_count 52）"\n      ],','        "note": "injected_ids 列表包含 sai-00079 与 sai-00080（injected_count 52）"}\n      ],','Close evidence object after note; no content change.'),
]


def main():
    records=[]
    for phase,provider,cid,old,new,reason in PATCHES:
        path=ROOT/'api'/phase/provider/cid/'visible-output.txt'
        original=path.read_text(encoding='utf-8')
        assert original.count(old)==1
        repaired=original.replace(old,new,1)
        value=json.loads(repaired)
        packet=read(ROOT/'packets'/f'{cid}.json')
        output=ROOT/'reviews/syntax-repaired'/provider/f'{cid}.json'
        save(output,value)
        records.append({'case_id':cid,'phase':phase,'provider':provider,'source_sha256':sha(path),
                        'old':old,'new':new,'reason':reason,'output_sha256':sha(output),
                        'validation_errors_after_repair':validate(value,packet),'reviewer':'primary Codex agent','new_api_calls':0})
    save(ROOT/'records/syntax-repairs.json',records)
    print(json.dumps({'syntax_repairs':len(records),'new_api_calls':0}))


if __name__=='__main__':main()
