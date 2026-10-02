"""Expose Hermes' real read/search tools with paths confined to the run workspace."""
import json
from pathlib import Path


def register_archive_files(work: Path, log: Path):
    from tools.registry import registry
    from tools import file_tools
    root=work.resolve()
    def wrap(name,handler):
        def guarded(args,**kwargs):
            args=dict(args)
            target=(root/str(args.get('path') or '.')).resolve()
            if target!=root and root not in target.parents:
                out=json.dumps({'error':'File access is limited to this isolated run workspace.'})
            elif name=='search_files' and args.get('target') in ('files','find') and ('..' in str(args.get('pattern','')).replace('\\','/').split('/') or ':' in str(args.get('pattern',''))):
                out=json.dumps({'error':'File patterns must stay inside the workspace.'})
            else:
                args['path']=str(target)
                out=handler(args,**kwargs)
            with log.open('a',encoding='utf-8') as f:f.write(json.dumps({'name':name,'arguments':args,'result':out},ensure_ascii=False)+'\n')
            return out
        return guarded
    for name,schema,handler in [('read_file',file_tools.READ_FILE_SCHEMA,file_tools._handle_read_file),
                                ('search_files',file_tools.SEARCH_FILES_SCHEMA,file_tools._handle_search_files)]:
        registry.register(name=name,toolset='lab_files',schema=schema,handler=wrap(name,handler),
                          check_fn=file_tools._check_file_reqs,override=True,max_result_size_chars=100_000)
