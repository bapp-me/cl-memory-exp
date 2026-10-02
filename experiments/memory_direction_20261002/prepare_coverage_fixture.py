"""Manual diagnostic correction using only counts already in the source note.

This is a simple comparison condition, not an implemented memory algorithm.
It does not contain the target question or its answer.
"""
import hashlib
from lab_common import ROOT, save_json

source=ROOT/'results/runs/v2-ds-a11-write-r1/memory_after'
dest=ROOT/'fixtures/coverage-diagnostic'
dest.mkdir(parents=True,exist_ok=True)
old='A "$N" threshold can be written either as `prc_usd <= N` or `prc <= 100*N`; both give identical row sets.'
new=('Equality is verified only on the intersection of non-null rows, not on all rows. '
     'Because 6,570 prices exist in `prc` but only 6,346 in `prc_usd`, the two columns cannot '
     'be substituted in an arbitrary threshold or aggregate without checking coverage. '
     'Select the column covering the requested population and then convert units; '
     'do not silently discard a known price just because its converted column is NULL.')
manifest={'type':'manual diagnostic; source-observation-only correction',
          'source_run':'v2-ds-a11-write-r1','target_answer_included':False,'files':[]}
for p in source.glob('*.md'):
    text=p.read_text(encoding='utf-8')
    if p.name=='environment.md':
        assert old in text
        text=text.replace(old,new)
    (dest/p.name).write_text(text,encoding='utf-8',newline='\n')
    manifest['files'].append({'name':p.name,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                             'new_sha256':hashlib.sha256((dest/p.name).read_bytes()).hexdigest()})
save_json(dest/'manifest.json',manifest)
