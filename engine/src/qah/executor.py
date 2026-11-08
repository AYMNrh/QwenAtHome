"""Reference adapter. QAH owns lifecycle and requests; llama.cpp owns math today."""
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


class ReferenceExecutor:
    def __init__(self, server, model, context, log, key_type='f16', value_type='f16',
                 gpu_layers=99, batch=512, threads=8, startup_timeout=180, request_timeout=1800,
                 ubatch=None, mtp_depth=0, prefix_cache=False, fit=False, backend_sampling=False,
                 draft_ubatch=None):
        self.log_path = Path(log)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.process = None
        self.log_file = None
        self.startup_timeout = startup_timeout
        self.request_timeout = request_timeout
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.url = 'http://127.0.0.1:%d' % port
        self.argv = [str(server), '--model', str(model), '--ctx-size', str(context),
                     '--host', '127.0.0.1', '--port', str(port), '--parallel', '1',
                     '--n-gpu-layers', str(gpu_layers), '--flash-attn', 'on',
                     '--cache-type-k', key_type, '--cache-type-v', value_type,
                     '--batch-size', str(batch), '--ubatch-size', str(batch if ubatch is None else ubatch),
                     '--threads', str(threads), '--fit', 'on' if fit else 'off',
                     '--spec-type', 'draft-mtp' if mtp_depth else 'none',
                     '--no-context-shift', '--cache-ram', '8192' if prefix_cache else '0',
                     '--ctx-checkpoints', '32' if prefix_cache else '0',
                     '--no-webui', '--verbosity', '4']
        if mtp_depth:
            self.argv += ['--spec-draft-n-max', str(mtp_depth),
                          '--spec-draft-type-k', 'q8_0', '--spec-draft-type-v', 'q8_0']
            if draft_ubatch is not None:
                self.argv += ['--spec-draft-n-ubatch', str(draft_ubatch)]
        if fit:
            self.argv += ['--fit-target', '512']
        if backend_sampling:
            self.argv += ['--backend-sampling']
        self.argv += ['--jinja']

    def __enter__(self):
        self.log_file = self.log_path.open('wb')
        try:
            self.process = subprocess.Popen(self.argv, stdout=self.log_file, stderr=subprocess.STDOUT,
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            start = time.perf_counter()
            while time.perf_counter() - start < self.startup_timeout:
                if self.process.poll() is not None:
                    raise RuntimeError('reference exited %s; see %s' % (self.process.returncode, self.log_path))
                try:
                    self.json('/health')
                    self.load_seconds = time.perf_counter() - start
                    return self
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.2)
            raise TimeoutError('reference startup timeout')
        except BaseException:
            self.close()
            raise

    def json(self, route, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(self.url + route, data, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=self.request_timeout if payload is not None else 2) as response:
            return json.load(response)

    def tokenize(self, text):
        return self.json('/tokenize', dict(content=text, add_special=False))['tokens']

    def chat(self, messages, generated, seed=42, cache=False):
        payload = dict(messages=messages, max_tokens=generated, seed=seed, temperature=0,
                       top_k=1, top_p=1.0, min_p=0.0, repeat_penalty=1.0,
                       chat_template_kwargs=dict(enable_thinking=False),
                       cache_prompt=cache, stream=False)
        start = time.perf_counter()
        response = self.json('/v1/chat/completions', payload)
        return dict(content=response['choices'][0]['message']['content'],
                    elapsed_seconds=time.perf_counter() - start,
                    ttft_seconds=None, response=response,
                    sampling={k: v for k, v in payload.items() if k != 'messages'})

    def complete(self, tokens, generated, seed, cache=False, force_length=False):
        payload = dict(prompt=tokens, n_predict=generated, seed=seed, temperature=0,
                       top_k=1, top_p=1.0, min_p=0.0, repeat_penalty=1.0,
                       cache_prompt=cache, stream=True, return_tokens=True,
                       id_slot=0, ignore_eos=force_length)
        req = urllib.request.Request(self.url + '/completion', json.dumps(payload).encode(),
                                     {'Content-Type': 'application/json'})
        start, first = time.perf_counter(), None
        content, output_tokens, final = [], [], None
        with urllib.request.urlopen(req, timeout=self.request_timeout) as response:
            for line in response:
                if not line.startswith(b'data: '):
                    continue
                body = line[6:].strip()
                if body == b'[DONE]':
                    break
                event = json.loads(body)
                if 'error' in event:
                    raise RuntimeError(str(event['error']))
                piece = event.get('content', '')
                ids = event.get('tokens', [])
                if first is None and (piece or ids):
                    first = time.perf_counter()
                content.append(piece)
                output_tokens.extend(ids)
                if event.get('stop'):
                    final = event
        if final is None:
            raise RuntimeError('stream ended without terminal completion event')
        # The request is reproducible from fixture + token hash; do not duplicate
        # hundreds of thousands of decoded prompt tokens in every terminal event.
        final.pop('prompt', None)
        return dict(content=''.join(content), output_token_ids=output_tokens,
                    ttft_seconds=None if first is None else first - start,
                    elapsed_seconds=time.perf_counter() - start, response=final,
                    sampling={k: v for k, v in payload.items() if k not in ('prompt',)})

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.log_file:
            self.log_file.close()

    def __exit__(self, *args):
        self.close()
