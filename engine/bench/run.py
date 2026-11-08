"""Isolated llama.cpp reference trials. Context sizes denote TOTAL capacity, not prompt size."""
import argparse
import hashlib
import json
import platform
import random
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qah.executor import ReferenceExecutor
from qah.memory import estimate
from qah.model import inspect_gguf, sha256
from qah.telemetry import Monitor, gpu_sample, host_inventory


def provenance():
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    digest = hashlib.sha256()
    for folder in ('src', 'bench', 'configs'):
        for file in sorted((ROOT / folder).rglob('*')):
            if file.is_file() and file.suffix in ('.py', '.json') and 'results' not in file.parts:
                digest.update(file.relative_to(ROOT).as_posix().encode())
                digest.update(file.read_bytes())
    return dict(commit_sha=result.stdout.strip() if result.returncode == 0 else None,
                source_sha256=digest.hexdigest(),
                git_status=subprocess.run(['git', 'status', '--porcelain=v1'], cwd=ROOT,
                                          capture_output=True, text=True).stdout)


def source_snapshot(path):
    files = {}
    for folder in ('src', 'bench', 'configs'):
        for file in sorted((ROOT / folder).rglob('*')):
            if file.is_file() and file.suffix in ('.py', '.json') and 'results' not in file.parts:
                files[file.relative_to(ROOT).as_posix()] = file.read_text(encoding='utf-8')
    path.write_text(json.dumps(files, indent=2), encoding='utf-8')


def allocations(log):
    found = {}
    events = {}
    try:
        text = Path(log).read_text(encoding='utf-8', errors='replace')
    except OSError as error:
        return dict(error=str(error))
    for device, kind, amount in re.findall(r'(\S+)\s+(model|KV|RS|compute) buffer size\s*=\s*([\d.]+) MiB', text):
        key = device + '_' + kind + '_bytes'
        encoded = round(float(amount) * 1024**2)
        events.setdefault(key, []).append(encoded)
        # Main and MTP caches coexist. Compute logs instead repeat reservations
        # and cannot be summed to infer simultaneous workspace or graph memory.
        found[key] = encoded if kind == 'compute' else sum(events[key])
    found['_logged_allocation_events_bytes'] = events
    found['_compute_scope'] = 'last logged reservation per device, not total live or peak workspace'
    return found


def hardware_inventory():
    argv = ['nvidia-smi', '--query-gpu=name,driver_version,memory.total,pcie.link.gen.current,pcie.link.width.current', '--format=csv']
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return dict(argv=argv, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    except (OSError, subprocess.TimeoutExpired) as error:
        return dict(argv=argv, error=str(error))


def make_prompt(executor, fixture, count, task, depth, seed):
    rng = random.Random(seed)
    answer = 'qah_' + ''.join(rng.choice('abcdefghjkmnpqrstuvwxyz23456789') for _ in range(16))
    spec = fixture[task]
    answer = spec.get('answer', answer)
    prefix = executor.tokenize('<|im_start|>system\nYou are a precise code assistant.\n<|im_end|>\n<|im_start|>user\n')
    needle = executor.tokenize(spec['needle'].format(answer=answer))
    suffix = executor.tokenize('\n' + spec['question'] + '\n<|im_end|>\n<|im_start|>assistant\n<think>\n</think>\n\n')
    needed = count - len(prefix) - len(needle) - len(suffix)
    if needed < 0:
        raise ValueError('prompt budget smaller than fixture')
    # A fixed varied block is repeated to bound tokenizer request size. Repetition is
    # disclosed: this is a controlled probe, not representative agent throughput.
    text = ''.join(fixture['filler'].format(i=i, team=i % 13) for i in range(256))
    block = executor.tokenize(text)
    if not block:
        raise ValueError('empty filler tokenization')
    filler = (block * ((needed + len(block) - 1) // len(block)))[:needed]
    position = int(needed * depth)
    tokens = prefix + filler[:position] + needle + filler[position:] + suffix
    assert len(tokens) == count
    return tokens, answer, dict(needle_token_offset=len(prefix) + position,
                                filler_block_tokens=len(block), repeated_filler=True,
                                chat_format='qwen im_start/im_end, closed think prefill')


def append(path, row):
    row['recorded_unix'] = time.time()
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps({k: row.get(k) for k in ('model_label', 'context', 'mtp_depth', 'trial', 'task', 'depth', 'phase', 'status', 'error')}, ensure_ascii=False), flush=True)


def evaluate(result, answer):
    response = result['response']
    generated = response.get('tokens_predicted')
    prompt = response.get('tokens_evaluated')
    timings = response.get('timings', {})
    return dict(result, generated_tokens=generated, backend_prompt_tokens=prompt,
                cached_input_tokens=timings.get('cache_n'),
                cached_tokens_after_request=response.get('tokens_cached'), timings=timings,
                accepted_output_tokens_per_second=timings.get('predicted_per_second'),
                retrieval_exact_match=result['content'].strip() == answer,
                expected=answer, mtp_acceptance=None)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', required=True)
    p.add_argument('--server', required=True)
    p.add_argument('--contexts', nargs='+', type=int, default=[8192, 32768, 86016, 131072, 262144, 524288])
    p.add_argument('--trials', type=int, default=3)
    p.add_argument('--generate', type=int, default=128)
    p.add_argument('--key-type', choices=['f16', 'q8_0', 'q4_0'], default='f16')
    p.add_argument('--value-type', choices=['f16', 'q8_0', 'q4_0'], default='f16')
    p.add_argument('--gpu-layers', type=int, default=99)
    p.add_argument('--tasks', nargs='+', choices=['retrieval', 'code', 'decode'], default=['retrieval', 'code', 'decode'])
    p.add_argument('--depths', nargs='+', type=float, default=[0.1, 0.5, 0.9])
    p.add_argument('--seed', type=int, default=1729)
    p.add_argument('--output', default='bench/results/reference.jsonl')
    p.add_argument('--startup-timeout', type=float, default=180)
    p.add_argument('--request-timeout', type=float, default=1800)
    p.add_argument('--no-reuse', action='store_true')
    p.add_argument('--allocation-only', action='store_true', help='load/warmup only; no prefill, decode or quality claim')
    args = p.parse_args()
    if args.trials < 1 or args.generate < 1 or any(not 0 <= d <= 1 for d in args.depths):
        p.error('positive trials/generate and depths in [0,1] required')
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model = inspect_gguf(args.model, checksum=True)
    fixture_path = ROOT / 'bench/fixtures/tasks.json'
    fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
    version = subprocess.run([args.server, '--version'], capture_output=True, text=True, timeout=30)
    base = dict(schema_version=1, run_id=str(uuid.uuid4()), provenance=provenance(),
                model_path=model['path'], model_sha256=model['sha256'],
                reference_version=version.stdout + version.stderr, reference_binary_sha256=sha256(args.server),
                fixture_sha256=sha256(fixture_path), seed=args.seed,
                key_type=args.key_type, value_type=args.value_type, gpu_layers=args.gpu_layers,
                attention_semantics='native hybrid; full history for dense layers; no context shift',
                kv_lossy=args.key_type.startswith('q') or args.value_type.startswith('q'),
                speculation='none', cli=vars(args),
                host=host_inventory(), os=platform.platform(), python=sys.version,
                hardware=hardware_inventory())
    snapshot = output.parent / (base['run_id'] + '-sources.json')
    source_snapshot(snapshot)
    base['source_snapshot'] = str(snapshot)
    for context in args.contexts:
        budget = estimate(model, context, args.key_type, args.value_type)
        if context > budget['architecture']['declared_context'] or context <= args.generate + 256:
            append(output, dict(base, context=context, phase='gate', status='unsupported', estimate=budget,
                                error='outside declared positional context or insufficient prompt budget'))
            continue
        gpu = gpu_sample()
        # Only refuse on a certain lower-bound violation for an all-GPU request.
        # Partial placement needs a backend tensor plan; do not guess its residency.
        gpu_lower_bound = budget['trunk_weight_bytes'] + budget['kv_bytes'] + budget['recurrent_bytes'] + budget['reserve_bytes']
        # Reference layer placement indexes include stored MTP blocks even when
        # speculation is disabled, plus the output-layer placement slot.
        all_layers = budget['architecture']['trunk_layers'] + budget['architecture']['mtp_layers'] + 1
        if args.gpu_layers >= all_layers and gpu and gpu_lower_bound > gpu['free']:
            append(output, dict(base, context=context, phase='gate', status='refused_budget',
                                estimate=budget, gpu_before=gpu, gpu_lower_bound_bytes=gpu_lower_bound,
                                error='GPU trunk weights + native state + 1 GiB reserve exceed currently free VRAM; shared tensor residency excluded'))
            continue
        for trial in range(args.trials):
            log = output.parent / ('%s-c%d-t%d.log' % (base['run_id'], context, trial))
            executor = ReferenceExecutor(args.server, args.model, context, log, args.key_type,
                                         args.value_type, args.gpu_layers,
                                         startup_timeout=args.startup_timeout,
                                         request_timeout=args.request_timeout)
            row = dict(base, context=context, trial=trial, estimate=budget,
                       reference_argv=executor.argv, raw_log=str(log), gpu_before=gpu,
                       allocation_succeeded=False, prefill_succeeded=None)
            try:
                with Monitor(executor) as monitor:
                    with executor:
                        row['load_seconds'] = executor.load_seconds
                        row['allocation_succeeded'] = True
                        if args.allocation_only:
                            append(output, dict(row, phase='allocation', status='allocated',
                                                backend_allocations=allocations(log), memory=monitor.report(),
                                                quality_pass=None, sustained_decode_complete=False))
                            continue
                        for task in args.tasks:
                            for depth in args.depths:
                                tokens, answer, details = make_prompt(executor, fixture, context - args.generate - 1,
                                                                      task, depth, args.seed + trial)
                                case = dict(row, task=task, depth=depth, prompt_tokens=len(tokens),
                                            prompt_sha256=hashlib.sha256(json.dumps(tokens).encode()).hexdigest(),
                                            fixture_details=details)
                                cold_result = None
                                for phase in (['cold'] if args.no_reuse else ['cold', 'warm_prefix', 'tool_turn']):
                                    if phase == 'tool_turn':
                                        # Controlled cache-locality probe with explicit message boundaries.
                                        # Full model-selected tool calls are a later API milestone.
                                        tool = executor.tokenize('3<|im_end|>\n<|im_start|>user\n' + fixture['tool_suffix'] +
                                                                 '\n<|im_end|>\n<|im_start|>assistant\n<think>\n</think>\n\n')
                                        tool_base, _, _ = make_prompt(executor, fixture,
                                            context - args.generate - len(tool) - 2,
                                            task, depth, args.seed + trial)
                                        executor.complete(tool_base, 1, args.seed + trial, cache=False)
                                        request_tokens = tool_base + tool
                                        expected = '3'
                                    else:
                                        request_tokens, expected = tokens, answer
                                    started = time.time()
                                    result = executor.complete(request_tokens, args.generate, args.seed + trial,
                                                               cache=phase != 'cold',
                                                               force_length=task == 'decode' and phase != 'tool_turn')
                                    data = evaluate(result, expected)
                                    if data['backend_prompt_tokens'] != len(request_tokens):
                                        raise RuntimeError('backend prompt token count differs from submitted token array')
                                    if task == 'decode' and phase != 'tool_turn':
                                        data['retrieval_exact_match'] = None
                                        data['expected'] = None
                                    if phase == 'cold':
                                        cold_result = result
                                    if phase == 'warm_prefix':
                                        data['deterministic_matches_cold'] = (
                                            result['content'] == cold_result['content'] and
                                            result['output_token_ids'] == cold_result['output_token_ids'])
                                    predicted = data['generated_tokens']
                                    append(output, dict(case, phase=phase, status='ok', started_unix=started,
                                                        prompt_tokens=len(request_tokens),
                                                        request_prompt_sha256=hashlib.sha256(json.dumps(request_tokens).encode()).hexdigest(),
                                                        measurement=data, memory=monitor.report(),
                                                        backend_allocations=allocations(log),
                                                        prefill_succeeded=True,
                                                        sustained_decode_complete=(task == 'decode' and phase != 'tool_turn' and
                                                            predicted == args.generate and not result['response'].get('truncated', False)),
                                                        quality_pass=data['retrieval_exact_match']))
                        # Allocation/residency messages remain in the unmodified log.
            except (OSError, ValueError, RuntimeError, TimeoutError) as error:
                append(output, dict(row, phase='execution', status='failed', error=repr(error),
                                    reference_exit_code=executor.process.poll() if executor.process else None,
                                    memory=monitor.report()))
            except KeyboardInterrupt:
                append(output, dict(row, phase='execution', status='cancelled',
                                    error='user/runner interrupt', memory=monitor.report()))
                raise


if __name__ == '__main__':
    main()
