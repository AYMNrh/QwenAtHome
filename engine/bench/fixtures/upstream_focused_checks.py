import ast, json, os, pathlib, re, subprocess, sys, time, urllib.request
ROOT=pathlib.Path(os.environ.get('BENCH_OUTPUT_DIR','benchmark-output')).resolve()
ROOT.mkdir(parents=True,exist_ok=True)
URL=os.environ.get('BENCH_URL','http://127.0.0.1:8081')
def post(path,data,timeout=300):
    req=urllib.request.Request(URL+path,json.dumps(data).encode(),{'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def ask(messages,limit=1600):
    t=time.perf_counter()
    r=post('/v1/chat/completions',dict(model=os.environ.get('MODEL_ALIAS','Qwen3.8-27B'),messages=messages,max_tokens=limit,temperature=0,seed=42,chat_template_kwargs={'enable_thinking':False}))
    return r,time.perf_counter()-t
CACHE='''class TTLCache:
    def __init__(self):
        self._items = {}

    def set(self, key, value, ttl, now):
        if ttl < 0:
            raise ValueError("negative ttl")
        self._items[key] = (value, now + ttl)

    def get(self, key, now, default=None):
        item = self._items.get(key)
        if item is None:
            return default
        value, expires = item
        if now > expires:
            del self._items[key]
            return default
        return value

    def purge(self, now):
        expired = [key for key, (_, expiry) in self._items.items() if now > expiry]
        for key in expired:
            del self._items[key]
        return len(expired)

    def delete(self, key):
        return self._items.pop(key, None) is not None
'''
CSV='''def escape_cell(value):
    text = "" if value is None else str(value)
    if any(char in text for char in (",", '"', "\\n", "\\r")):
        return '"' + text.replace('"', '""') + '"'
    return text


def format_row(values):
    return ",".join(escape_cell(value) for value in values)


def export_csv(rows, header=None):
    lines = []
    if header is not None:
        lines.append(format_row(header))
    lines.extend(format_row(row) for row in rows)
    return "\\n".join(lines) + ("\\n" if lines else "")
'''
TASKS=[
 ('bugfix','Fix expiry semantics in this cache: an entry is expired when now >= its expiry, including ttl=0. Fix get and purge consistently. Preserve all other behavior and signatures. Return the complete module.\n'+CACHE,
 '''c=TTLCache(); c.set("a",7,5,10); assert c.get("a",14)==7; assert c.get("a",15,"missing")=="missing"; c.set("zero",1,0,20); assert c.get("zero",20) is None; c.set("b",2,3,20); assert c.purge(23)==1; assert c.purge(23)==0'''),
 ('multi_function_edit','Extend this CSV module: add delimiter="," as an optional keyword to all three functions and newline="\\n" to export_csv. Propagate the chosen delimiter everywhere. Quote fields containing that delimiter, quotes, CR, or LF, double embedded quotes, retain None as empty, and do not mutate rows. Default behavior and positional arguments must remain compatible. Return the complete module.\n'+CSV,
 '''rows=[["a;b",'x"y',None],["plain","next",2]]; original=[r[:] for r in rows]; assert export_csv(rows,header=["A","B","C"],delimiter=";",newline="\\r\\n")== 'A;B;C\\r\\n"a;b";"x""y";\\r\\nplain;next;2\\r\\n'; assert rows==original; assert format_row(["a,b",None])=='"a,b",'; assert export_csv([])==""'''),
 ('fresh_code','Implement merge_sorted_events(streams): a lazy generator merging any number of already-sorted iterables of dicts with numeric timestamp keys. Ascending timestamps; ties keep lower stream index first and original order within that stream. Preserve the original dict objects and do not mutate inputs. Empty streams work. Do not materialize streams: read at most one pending event per stream. Use heapq and the standard library only. Return a complete Python module without demonstrations.',
 '''a={"timestamp":1,"id":"a"}; b={"timestamp":2,"id":"b"}; c={"timestamp":1,"id":"c"}; d={"timestamp":2,"id":"d"}; count=[0];
def stream():
    for e in [a,b]:
        count[0]+=1
        yield e
g=merge_sorted_events([stream(),[c,d],[]]); assert count[0]==0; assert next(g) is a; assert count[0]==1; assert list(g)==[c,b,d]; assert list(merge_sorted_events([]))==[]''')]
def validate(source,test,name):
    source=source.strip()
    if source.startswith('```'):
        match=re.search(r'```(?:python)?\s*\n(.*?)```',source,re.S)
        if not match:return False,'incomplete code fence'
        source=match.group(1)
    try:
        tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                modules=[x.name.split('.')[0] for x in node.names] if isinstance(node,ast.Import) else [(node.module or '').split('.')[0]]
                if any(m not in {'heapq','typing','collections','itertools','decimal','csv','io'} for m in modules):raise ValueError('unexpected import')
            if isinstance(node,ast.Name) and node.id in {'open','exec','eval','compile','__import__','globals','locals','getattr','setattr','input','breakpoint','exit','quit'}:raise ValueError('unexpected capability')
            if isinstance(node,ast.Attribute) and node.attr.startswith('__'):raise ValueError('unexpected dunder access')
        file=ROOT/(name+'.py'); file.write_text(source+'\n\n'+test+'\n',encoding='utf-8')
        run=subprocess.run([sys.executable,'-I',str(file)],capture_output=True,text=True,timeout=8)
        return run.returncode==0,run.stderr[-700:]
    except (SyntaxError,ValueError,subprocess.TimeoutExpired) as e:return False,str(e)
def coding(profile):
    results=[]
    for name,prompt,test in TASKS:
        r,wall=ask([{'role':'user','content':'Return only executable Python code, no explanation or markdown.\n'+prompt}])
        text=r['choices'][0]['message']['content']; ok,error=validate(text,test,f'qwen38-{profile}-{name}')
        row=dict(profile=profile,task=name,passed=ok,error=error,finish=r['choices'][0]['finish_reason'],wall_seconds=wall,timings=r.get('timings',{}),usage=r.get('usage',{}),text=text)
        results.append(row); print(json.dumps({k:v for k,v in row.items() if k!='text'}),flush=True)
        (ROOT/f'qwen38-real-{profile}.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
def context_checks():
    import random, threading
    rng=random.Random(4827)
    filler='\n'.join(f'Archive entry {i:06}: ticket {rng.getrandbits(48):012x}; project group {i%37}; allocation {rng.randrange(10,9999)}; state reviewed.' for i in range(5000))
    tokens=post('/tokenize',{'content':filler,'add_special':False})['tokens']
    expected={'start':'HIGHLAND-483','middle':'AMBER-729','end':'WILLOW-916'}
    results=[]
    targets=tuple(map(int,sys.argv[2:])) or (8192,16384,32000)
    for target in targets:
        n=target-170
        left=post('/detokenize',{'tokens':tokens[:n//2]})['content']
        right=post('/detokenize',{'tokens':tokens[n//2:n]})['content']
        content='Reference lookup task. The archive entries are context only. Remember the three REFERENCE values.\nREFERENCE start = HIGHLAND-483\n'+left+'\nREFERENCE middle = AMBER-729\n'+right+'\nREFERENCE end = WILLOW-916\nReturn a JSON object with keys start, middle, end and their REFERENCE values. Output JSON only.'
        messages=[{'role':'user','content':content}]
        for phase in ('cold','resumed'):
            samples=[]; done=threading.Event()
            def monitor():
                while not done.is_set():
                    r=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
                    if r.returncode==0:
                        fields=r.stdout.strip().split(','); samples.append([int(x.strip()) for x in fields])
                    done.wait(.75)
            thread=threading.Thread(target=monitor,daemon=True); thread.start()
            try:r,wall=ask(messages,128)
            finally:done.set(); thread.join(timeout=6)
            text=r['choices'][0]['message']['content']
            try:
                match=re.search(r'\{.*\}',text,re.S); parsed=json.loads(match.group(0)) if match else None
            except json.JSONDecodeError:parsed=None
            row=dict(target=target,phase=phase,passed=parsed==expected,answer=text,wall_seconds=wall,timings=r.get('timings',{}),usage=r.get('usage',{}),peak_vram_mib=max((s[0] for s in samples),default=None),minimum_free_vram_mib=min((s[1] for s in samples),default=None))
            results.append(row); print(json.dumps(row),flush=True)
            output='qwen38-q3-context-checks.json' if max(targets)>32000 else 'qwen38-context-checks.json'
            (ROOT/os.environ.get('CONTEXT_RESULTS',output)).write_text(json.dumps(results,indent=2),encoding='utf-8')
            messages.extend([{'role':'assistant','content':text},{'role':'user','content':'Return those same three reference values again as JSON, ordering keys end, middle, start. JSON only.'}])
if __name__=='__main__':
    if sys.argv[1]=='context':context_checks()
    else:coding(sys.argv[1])

