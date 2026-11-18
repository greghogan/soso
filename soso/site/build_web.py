"""Build an event reader selected from manifests/events.json, then finish catalog navigation."""
from pathlib import Path
import argparse, os, subprocess, sys
from .event_registry import load, command
ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('event')
    parser.add_argument('--year', type=int, help='Required when an event has several registered years')
    args = parser.parse_args()
    entries = [e for e in load(ROOT) if e['slug'] == args.event and (args.year is None or e['year'] == args.year)]
    if len(entries) != 1:
        parser.error('Select exactly one registered event/year with EVENT --year YEAR')
    event = entries[0]
    env = dict(os.environ, SOSO_EVENT_DIR=str(ROOT/event['path']))
    env.pop('SOSO_STAGE_OUTPUTS', None)
    env['SOSO_EVENT_OUTPUT_DIR'] = str(ROOT/'build/direct'/event['path'])
    subprocess.run(command(ROOT, event, event['web_build'], sys.executable), check=True, cwd=ROOT, env=env)
    subprocess.run([sys.executable, '-m', 'soso.site.build_catalog'], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
