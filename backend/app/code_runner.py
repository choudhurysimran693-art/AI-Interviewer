"""Run candidate programs only in disposable, resource-limited Docker containers."""
import asyncio
import json
import shutil
import uuid


class RuntimeUnavailable(Exception):
    pass


IMAGES = {'python': 'python:3.12-alpine', 'javascript': 'node:22-alpine', 'c': 'gcc:14-bookworm', 'cpp': 'gcc:14-bookworm', 'java': 'eclipse-temurin:21-jdk'}
LIMIT = 16384
slots = asyncio.Semaphore(2)
PYTHON = "import sys,json\np=json.load(sys.stdin)\nns={}\nexec(p['code'],ns)\nprint(json.dumps(ns['solve'](p['input'])))"
JAVASCRIPT = "const p=JSON.parse(require('fs').readFileSync(0,'utf8')); const solve=new Function(p.code+'; return solve;')(); console.log(JSON.stringify(solve(p.input)));"


async def execute(language, code, data):
    docker = shutil.which('docker')
    if not docker:
        raise RuntimeUnavailable('Code runtime unavailable. Install and start Docker, then prepare the Python and JavaScript images described in docs/code-runtime.md.')
    if language not in IMAGES:
        raise ValueError('Choose Python, JavaScript, C, C++, or Java.')
    name = 'interview-code-' + uuid.uuid4().hex
    command = [docker, 'run', '--rm', '--pull=never', '--name', name, '--network=none',
               '--memory=128m', '--memory-swap=128m', '--cpus=0.5', '--pids-limit=32',
               '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
               '--user=65534:65534', '-i', IMAGES[language]]
    if language == 'python': command += ['python', '-I', '-c', PYTHON]
    elif language == 'javascript': command += ['node', '-e', JAVASCRIPT]
    else: raise ValueError('C, C++, and Java runners require a language-specific starter contract.')
    async with slots:
        proc = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
                                                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        async def read(stream):
            output = bytearray()
            while True:
                chunk = await stream.read(4096)
                if not chunk: return bytes(output)
                output.extend(chunk)
                if len(output) > LIMIT: raise OverflowError()
        async def communicate():
            proc.stdin.write(json.dumps({'code':code,'input':data}).encode())
            await proc.stdin.drain()
            proc.stdin.close()
            out, err = await asyncio.gather(read(proc.stdout), read(proc.stderr))
            await proc.wait()
            return out, err
        try:
            out, err = await asyncio.wait_for(communicate(), 8)
            if proc.returncode in (125,126,127):
                raise RuntimeUnavailable('Docker runtime is not ready. Start Docker and prepare the runner images; your answer has not been graded.')
            if proc.returncode: return {'status':'runtime_error'}
            try: return {'status':'ok','actual':json.loads(out)}
            except (ValueError, UnicodeError): return {'status':'invalid_output'}
        except asyncio.TimeoutError: return {'status':'time_limit'}
        except OverflowError: return {'status':'output_limit'}
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            cleanup = await asyncio.create_subprocess_exec(docker, 'rm', '-f', name,
                         stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            try: await asyncio.wait_for(cleanup.wait(), 3)
            except asyncio.TimeoutError: cleanup.kill(); await cleanup.wait()


def equal(actual, expected):
    if isinstance(expected, bool) or isinstance(actual, bool): return type(actual) is type(expected) and actual == expected
    if isinstance(expected, list): return isinstance(actual, list) and len(actual)==len(expected) and all(equal(a,b) for a,b in zip(actual,expected))
    if isinstance(expected, dict): return isinstance(actual,dict) and actual.keys()==expected.keys() and all(equal(actual[k],v) for k,v in expected.items())
    return actual == expected


async def grade(rubric, language, code, include_hidden=False):
    if language not in ('python','javascript'): raise ValueError('Executable assessments currently support Python and JavaScript.')
    samples=[]; hidden_passed=0
    for case in rubric['sample_tests']:
        result=await execute(language,code,case['input'])
        passed=result['status']=='ok' and equal(result.get('actual'),case['expected'])
        samples.append({**case,**result,'passed':passed})
    hidden=rubric.get('hidden_tests',[]) if include_hidden else []
    for case in hidden:
        result=await execute(language,code,case['input'])
        hidden_passed+=int(result['status']=='ok' and equal(result.get('actual'),case['expected']))
    # Never return hidden inputs, expected values, stdout, or exceptions.
    passed=sum(x['passed'] for x in samples)+hidden_passed
    total=len(samples)+len(hidden)
    return {'samples':samples,'hidden_passed':hidden_passed,'hidden_total':len(hidden),
            'passed':passed,'total':total,'score':round(100*passed/total) if total else 0}
