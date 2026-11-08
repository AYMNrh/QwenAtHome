"""Aggregate comparable successful trials; preserve failures and unknown quality."""
import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def stats(values):
    values = sorted(v for v in values if v is not None)
    return None if not values else dict(n=len(values), median=statistics.median(values),
                                       p95=values[max(0, math.ceil(len(values) * .95) - 1)])


def summarize(rows):
    groups = defaultdict(list)
    for r in rows:
        key = (r['model_sha256'], r['provenance']['source_sha256'], r.get('reference_binary_sha256'),
               r['context'], r.get('key_type'), r.get('value_type'), r.get('gpu_layers'),
               r.get('task'), r.get('depth'), r.get('phase'),
               json.dumps(r.get('cli', {}), sort_keys=True), r.get('mtp_depth'), r.get('speculation'))
        groups[key].append(r)
    result = []
    for key, group in groups.items():
        good = [r for r in group if r['status'] == 'ok']
        measured = [r['measurement'] for r in good]
        result.append(dict(model_sha256=key[0], source_sha256=key[1], context=key[3],
                           key_type=key[4], value_type=key[5], gpu_layers=key[6],
                           task=key[7], depth=key[8], phase=key[9],
                           mtp_depth=key[11], speculation=key[12],
                           trials=len(group), successes=len(good),
                           outcomes=[r['status'] for r in group],
                           quality_passes=sum(r.get('quality_pass') is True for r in good),
                           quality_measured=sum(r.get('quality_pass') is not None for r in good),
                           sustained_decode_complete=sum(r.get('sustained_decode_complete') is True for r in good),
                           ttft_seconds=stats(m.get('ttft_seconds') for m in measured),
                           elapsed_seconds=stats(m.get('elapsed_seconds') for m in measured),
                           accepted_output_tokens_per_second=stats(m.get('accepted_output_tokens_per_second') for m in measured),
                           prompt_tokens_per_second=stats(m.get('timings', {}).get('prompt_per_second') for m in measured)))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input')
    p.add_argument('--output')
    args = p.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text(encoding='utf-8').splitlines() if line.strip()]
    text = json.dumps(summarize(rows), indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
