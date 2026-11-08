"""Matched Q3_K_XL vs preferred Huihui abliterated reference experiments."""
import argparse
import hashlib
import importlib.util
import json
import os
import random
import subprocess
import time
import uuid
from pathlib import Path

from run import ROOT, allocations, append, hardware_inventory, provenance, source_snapshot
from qah.executor import ReferenceExecutor
from qah.model import architecture, inspect_gguf, sha256
from qah.telemetry import Monitor, gpu_sample, host_inventory

MODELS = {
    'huihui': ('Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf',
               'eea0638e283433e27b0edbd409b552be467a75ecc777d91c51db554c0a644c19'),
    'q3': ('Qwen3.8-27B-UD-Q3_K_XL.gguf',
           '8c2a45ff85e7674ca185ec8eb6cdeab0e617ed9d8018caed0b64380eb2a67a5e')}


def metrics(result):
    response = result['response']
    timings = response.get('timings', {})
    usage = response.get('usage', {})
    drafted, accepted = timings.get('draft_n'), timings.get('draft_n_accepted')
    return dict(result, timings=timings,
                prompt_tokens=usage.get('prompt_tokens', response.get('tokens_evaluated')),
                generated_tokens=usage.get('completion_tokens', response.get('tokens_predicted')),
                cached_input_tokens=usage.get('prompt_tokens_details', {}).get('cached_tokens', timings.get('cache_n')),
                accepted_output_tokens_per_second=timings.get('predicted_per_second'),
                mtp_acceptance=None if drafted is None else dict(drafted=drafted, accepted=accepted,
                    rate=accepted / drafted if drafted and accepted is not None else None),
                output_sha256=hashlib.sha256(result['content'].encode()).hexdigest())


def retrieval_prompt(executor, count, seed, purpose='retrieval'):
    rng = random.Random(seed)
    marker = 'qah_' + ''.join(rng.choice('abcdefghjkmnpqrstuvwxyz23456789') for _ in range(16))
    # Model's own template, not a manually composed approximation.
    sentinel = 'QAH_ARCHIVE_INSERTION_58279'
    question = ('Return only the exact RELEASE_SIGNING_KEY value, without code or explanation.'
                if purpose == 'retrieval' else
                'Write a complete Python parser for these archive entries, with input validation, '
                'a command-line interface and usage examples. Return the complete implementation.')
    content = 'Read this archive and remember RELEASE_SIGNING_KEY.\n' + sentinel + '\n' + question
    rendered = executor.json('/apply-template', dict(messages=[dict(role='user', content=content)],
                        chat_template_kwargs=dict(enable_thinking=False)))['prompt']
    if rendered.count(sentinel) != 1:
        raise ValueError('template did not preserve unique insertion sentinel')
    left, right = rendered.split(sentinel)
    prefix, suffix = executor.tokenize(left), executor.tokenize(right)
    needle = executor.tokenize('\nRELEASE_SIGNING_KEY = "' + marker + '"\n')
    count_filler = count - len(prefix) - len(needle) - len(suffix)
    if count_filler < 0:
        raise ValueError('insufficient retrieval prompt budget')
    filler_text = ''.join('Archive %06d: project=%02d ticket=%012x reviewed=true.\n' %
                         (i, i % 37, rng.getrandbits(48)) for i in range(1024))
    block = executor.tokenize(filler_text)
    filler = (block * ((count_filler + len(block) - 1) // len(block)))[:count_filler]
    middle = count_filler // 2
    tokens = prefix + filler[:middle] + needle + filler[middle:] + suffix
    assert len(tokens) == count
    return tokens, marker, dict(needle_offset=len(prefix) + middle, repeated_filler=True,
                               purpose=purpose, template_sha256=hashlib.sha256(rendered.encode()).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--models', nargs='+', choices=MODELS, default=['huihui', 'q3'])
    p.add_argument('--model-dir', default=os.environ.get('MODEL_DIR', 'models'))
    p.add_argument('--server', default=os.environ.get('LLAMA_SERVER', 'llama-server'))
    p.add_argument('--contexts', nargs='+', type=int, default=[32768])
    p.add_argument('--depths', nargs='+', type=int, default=[0, 3], help='MTP drafting depth (0 disables)')
    p.add_argument('--trials', type=int, default=3)
    p.add_argument('--tasks', nargs='+', choices=['coding', 'retrieval', 'decode'], default=['coding', 'retrieval', 'decode'])
    p.add_argument('--gpu-layers', type=int, default=99)
    p.add_argument('--draft-ubatch', type=int, default=None,
                   help='explicit MTP physical microbatch; default inherits target microbatch 128')
    p.add_argument('--allow-memory-pressure', action='store_true',
                   help='explicitly allow a failed reference fit-margin check; default refuses before prefill')
    p.add_argument('--output', default='bench/results/model-comparison.jsonl')
    args = p.parse_args()
    if args.trials < 1 or any(d < 0 or d > 8 for d in args.depths):
        p.error('positive trials and MTP depths 0..8 required')
    if args.draft_ubatch is not None and args.draft_ubatch < 1:
        p.error('draft microbatch must be positive')
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    # Capture sources before hashing multi-GB models; freeze code while running.
    prov = provenance()
    snapshot = output.parent / (run_id + '-sources.json')
    source_snapshot(snapshot)
    fixture_path = ROOT / 'bench/fixtures/upstream_focused_checks.py'
    os.environ['BENCH_OUTPUT_DIR'] = str(output.parent / (run_id + '-generated'))
    spec = importlib.util.spec_from_file_location('focused_fixtures', fixture_path)
    focused = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(focused)
    version = subprocess.run([args.server, '--version'], capture_output=True, text=True, timeout=30)
    base = dict(schema_version=1, run_id=run_id, provenance=prov, source_snapshot=str(snapshot),
                reference_version=version.stdout + version.stderr, reference_binary_sha256=sha256(args.server),
                fixture_sha256=sha256(fixture_path), fixture_upstream_blob='4860d114b71f43954b077476bab853535ac3428f',
                fixture_source='https://github.com/AYMNrh/QwenAtHome/blob/main/benchmarks/focused_checks.py',
                host=host_inventory(), hardware=hardware_inventory(), cli=vars(args),
                key_type='q4_0', value_type='q4_0', kv_lossy=True, gpu_layers=args.gpu_layers,
                seed=42, attention_semantics='native hybrid, dense full history, no context shifting')
    for label in args.models:
        name, expected_checksum = MODELS[label]
        model = inspect_gguf(Path(args.model_dir) / name, checksum=True)
        if model['sha256'] != expected_checksum:
            raise ValueError('model checksum differs from retained upstream baseline: ' + name)
        arch = architecture(model)
        audit = output.parent / ('%s-%s-model.json' % (run_id, label))
        audit.write_text(json.dumps(model, indent=2), encoding='utf-8')
        for context in args.contexts:
            for depth in args.depths:
                row = dict(base, model_label=label, preferred=label == 'huihui', model_path=model['path'],
                           model_sha256=model['sha256'], model_audit=str(audit), context=context, mtp_depth=depth,
                           draft_ubatch=args.draft_ubatch,
                           speculation='draft-mtp' if depth else 'none')
                if context > arch['declared_context'] or (depth and not arch['mtp_layers']):
                    append(output, dict(row, phase='gate', status='unsupported'))
                    continue
                log = output.parent / ('%s-%s-c%d-mtp%d.log' % (run_id, label, context, depth))
                executor = ReferenceExecutor(args.server, model['path'], context, log, 'q4_0', 'q4_0',
                    gpu_layers=args.gpu_layers, ubatch=128, mtp_depth=depth,
                    prefix_cache=True, fit=True, backend_sampling=True, draft_ubatch=args.draft_ubatch)
                row.update(reference_argv=executor.argv, raw_log=str(log), gpu_before=gpu_sample())
                try:
                    with Monitor(executor) as monitor:
                        with executor:
                            fit_failed = 'failed to fit params to free device memory' in log.read_text(
                                encoding='utf-8', errors='replace')
                            row['reference_fit_margin_failed'] = fit_failed
                            if fit_failed and not args.allow_memory_pressure:
                                append(output, dict(row, phase='gate', status='refused_budget',
                                    error='Reference fitter cannot meet requested 512 MiB reserve; no prefill attempted',
                                    backend_allocations=allocations(log), memory=monitor.report()))
                                continue
                            for trial in range(args.trials):
                                if 'coding' in args.tasks:
                                    for task, prompt, check in focused.TASKS:
                                        messages = [dict(role='user', content='Return only executable Python code, no explanation or markdown.\n' + prompt)]
                                        result = metrics(executor.chat(messages, 1600, seed=42, cache=False))
                                        passed, error = focused.validate(result['content'], check,
                                            '%s-c%d-m%d-t%d-%s' % (label, context, depth, trial, task))
                                        append(output, dict(row, trial=trial, task=task, phase='cold', status='ok',
                                            quality_pass=passed, validation_error=error, measurement=result,
                                            prompt_tokens=result['prompt_tokens'], memory=monitor.report(),
                                            backend_allocations=allocations(log), sustained_decode_complete=False))
                                if 'retrieval' in args.tasks:
                                    tokens, answer, details = retrieval_prompt(executor, context - 257, 42 + trial)
                                    for phase in ('cold', 'warm_prefix'):
                                        result = metrics(executor.complete(tokens, 128, seed=42, cache=phase != 'cold'))
                                        if result['prompt_tokens'] != len(tokens):
                                            raise RuntimeError('backend retrieval prompt count differs from submitted tokens')
                                        append(output, dict(row, trial=trial, task='retrieval', phase=phase, status='ok',
                                            quality_pass=result['content'].strip() == answer, expected=answer,
                                            prompt_tokens=len(tokens), prompt_sha256=hashlib.sha256(json.dumps(tokens).encode()).hexdigest(),
                                            fixture_details=details, measurement=result, memory=monitor.report(),
                                            backend_allocations=allocations(log), sustained_decode_complete=False))
                                if 'decode' in args.tasks:
                                    tokens, _, details = retrieval_prompt(executor, context - 257, 42 + trial, purpose='decode')
                                    result = metrics(executor.complete(tokens, 128, seed=42, cache=False, force_length=True))
                                    if result['prompt_tokens'] != len(tokens):
                                        raise RuntimeError('backend decode prompt count differs from submitted tokens')
                                    append(output, dict(row, trial=trial, task='decode', phase='cold', status='ok',
                                        quality_pass=None, prompt_tokens=len(tokens),
                                        prompt_sha256=hashlib.sha256(json.dumps(tokens).encode()).hexdigest(),
                                        fixture_details=details, measurement=result, memory=monitor.report(),
                                        backend_allocations=allocations(log), sustained_decode_complete=(
                                            result['generated_tokens'] == 128 and not result['response'].get('truncated', False))))
                except (OSError, ValueError, RuntimeError, TimeoutError) as error:
                    append(output, dict(row, phase='execution', status='failed', error=repr(error), memory=monitor.report()))
                except KeyboardInterrupt:
                    append(output, dict(row, phase='execution', status='cancelled', error='interrupt', memory=monitor.report()))
                    raise


if __name__ == '__main__':
    main()
