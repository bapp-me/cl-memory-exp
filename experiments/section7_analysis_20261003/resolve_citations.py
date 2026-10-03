"""Resolve literal quotes inside decoded JSON string leaves; never fuzzy-match."""
from collections import Counter
from common import *
from audit_reviews import get_review


def leaves(value,pointer='',depth=0):
    if depth>8:return
    if isinstance(value,str):
        yield pointer,value
        if value.lstrip().startswith(('{','[')):
            try:decoded=json.loads(value)
            except ValueError:return
            yield from leaves(decoded,pointer+'/$decoded',depth+1)
    elif isinstance(value,list):
        for i,x in enumerate(value):yield from leaves(x,pointer+'/'+str(i),depth+1)
    elif isinstance(value,dict):
        for k,x in value.items():yield from leaves(x,pointer+'/'+str(k).replace('~','~0').replace('/','~1'),depth+1)


def main():
    results=[];counts=Counter()
    for case in read(ROOT/'records/manifest.json')['cases']:
        obj=get_review(case);packet=read(ROOT/'packets'/f'{case["case_id"]}.json')
        texts={s['id']:s['text'] for s in packet['evidence']};expanded={k:list(leaves(v)) for k,v in texts.items()};refs=[]
        claims=[(f'labels/{i}',x) for i,x in enumerate(obj.get('labels',[]))]+[(f'semantic/{k}',v) for k,v in obj.get('semantic',{}).items() if isinstance(v,dict)]
        for claim_path,claim in claims:
            for i,ref in enumerate(claim.get('evidence',[])):
                section=ref.get('section');quote=ref.get('quote');matches=[]
                if quote:
                    matches=[{'json_pointer':ptr,'char_start':text.find(quote),'char_end':text.find(quote)+len(quote)} for ptr,text in expanded.get(section,[]) if quote in text]
                status='literal_section' if quote and quote in texts.get(section,'') else 'exact_decoded_leaf' if matches else 'unresolved'
                counts[status]+=1
                refs.append({'claim_path':claim_path,'evidence_index':i,'section':section,'quote':quote,'resolution':status,'matches':matches[:5]})
        results.append({'case_id':case['case_id'],'method':case['method'],'benchmark':case['benchmark'],'all_references_resolve':all(r['resolution']!='unresolved' for r in refs),'references':refs})
    save(ROOT/'records/citation-resolution.json',{'cases':results,'summary':dict(counts),'fully_resolved_cases':sum(x['all_references_resolve'] for x in results),
         'rule':'Exact substring in raw section or recursively JSON-decoded string leaf, with path/offset. No fuzzy matching, whitespace editing or invented text.',
         'limit':'Location verification does not validate semantic inference. Unresolved citations remain errors in the original strict audit.'})
    print(json.dumps({'references':dict(counts),'fully_resolved_cases':sum(x['all_references_resolve'] for x in results)}))


if __name__=='__main__':main()
