#!/usr/bin/env python3
"""Build the offline deliverable from local authoring modules; no dependencies."""
from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('model.js', 'rack-catalog.js', 'rack.js', 'logical.js', 'analysis.js', 'workbench.js', 'app.js')


def build(output=None, check=False):
    shell = (ROOT/'src'/'shell.html').read_text(encoding='utf-8')
    schema = json.loads((ROOT/'src'/'architecture-schema.json').read_text(encoding='utf-8'))
    scripts = []
    for name in MODULES:
        path = ROOT/'src'/name
        if not path.exists():
            raise ValueError('Missing authoring module: '+name)
        source = path.read_text(encoding='utf-8')
        if name == 'model.js':
            source, count = re.subn(r'const ARCH_SCHEMA\s*=\s*[^;]*__ARCHITECTURE_SCHEMA__\s*;', lambda _: 'const ARCH_SCHEMA = '+json.dumps(schema,separators=(',',':'),ensure_ascii=True)+';', source)
            if count != 1:
                raise ValueError('model.js must contain one architecture schema insertion point.')
        # HTML parsers terminate script elements even inside a JS string.
        source = re.sub(r'</script', r'<\/script', source, flags=re.I)
        scripts.append('<script>\n'+source.rstrip()+'\n</script>')
    matches = list(re.finditer(r'<!-- INLINE:[\w.-]+ -->',shell))
    if not matches:
        raise ValueError('The shell needs authoring module markers.')
    notices = (ROOT/'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
    notices = re.sub(r'</script', r'<\/script', notices, flags=re.I)
    result = shell[:matches[0].start()]+'\n'.join(scripts)+'\n<script id="third-party-notices" type="text/plain">\n'+notices+'\n</script>'+shell[matches[-1].end():]
    if '<script id="project-data" type="application/json">null</script>' not in result:
        raise ValueError('Public source must not embed a real project.')
    target = Path(output) if output else ROOT/'design-studio'/'index.html'
    if check:
        if not target.exists() or target.read_text(encoding='utf-8') != result:
            raise ValueError('The distributable is stale. Run python3 tools/build_app.py.')
    else:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(result,encoding='utf-8')
    return target


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:
        print(build(args.output,args.check))
    except (ValueError,OSError,json.JSONDecodeError) as error:
        parser.exit(1,str(error)+'\n')
