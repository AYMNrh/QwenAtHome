"""Reproducible inventory, model directory audit and memory estimates."""
import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from qah.model import inspect_gguf
from qah.memory import estimate
from qah.telemetry import host_inventory


def command(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return dict(argv=args, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
    except (OSError, subprocess.TimeoutExpired) as error:
        return dict(argv=args, error=str(error))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--checksum', action='store_true')
    p.add_argument('--server')
    args = p.parse_args()
    model = inspect_gguf(args.model, args.checksum)
    report = dict(model=model, os=platform.platform(), python=sys.version, host=host_inventory(),
                  inventory=[command(['git', 'status', '--short', '--branch']),
                             command(['git', 'rev-parse', 'HEAD']),
                             command(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version,pcie.link.gen.current,pcie.link.width.current', '--format=csv']),
                             command(['nvcc', '--version'])], estimates=[])
    if args.server:
        report['inventory'].append(command([args.server, '--version']))
    for context in (8192, 32768, 86016, 131072, 262144, 524288):
        for kind in ('f16', 'q8_0', 'q4_0'):
            report['estimates'].append(estimate(model, context, kind, kind,
                                               gpu_budget_bytes=16303 * 1024**2))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(architecture=model['metadata']['general.architecture'],
                          tensors=len(model['tensors']), tensor_bytes=model['tensor_bytes'],
                          sha256=model['sha256'], output=str(out))))


if __name__ == '__main__':
    main()
