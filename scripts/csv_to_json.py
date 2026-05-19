#!/usr/bin/env python3
"""Convert Gemini's K-Rain dashboard CSV export into canonical controllers.json.

Usage:
  python scripts/csv_to_json.py path/to/irrigation_schedule_YYYY-MM-DD.csv [--out data/controllers.json]

Input CSV columns:
  module, program, calendar, days, water_budget, start_time,
  station_number, station_name, duration_hours, duration_minutes, duration_total_mins

Output JSON shape:
{
  "generated_at": "2026-05-08T...",
  "source": "K-Rain dashboard via Gemini agent",
  "controllers": [
    {
      "id": "front-lawn-4",
      "name": "Front-Lawn-4",
      "type": "krain",
      "programs": [
        {
          "id": "front-lawn-4__rotors",
          "name": "Rotors",
          "calendar": "Custom",
          "days": ["Monday", ..., "Sunday"],
          "water_budget": 100,
          "start_times": ["02:00", "14:45"],
          "stations": [
            { "number": 1, "name": "Station 1", "duration_min": 20 },
            ...
          ]
        }
      ]
    }
  ]
}
"""
import argparse, csv, json, re, sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

DEFAULT_CHECK = [{"text": "Heads aligned / No mist / No leaks / Coverage even / Pressure OK", "done": False}]


def load_existing_station_registry(out_path):
    """Return {controller_id: {station_num: station_dict}} from existing JSON so user edits survive regen."""
    p = Path(out_path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except Exception:
        return {}
    return {
        c['id']: {s['number']: s for s in c.get('stations', [])}
        for c in data.get('controllers', [])
    }


def build_station_registry(programs, preserved):
    """Dedup physical stations across programs; preserve user fields from `preserved` dict."""
    physical = {}
    for prog in programs:
        for s in prog.get('stations', []):
            n = s['number']
            if n not in physical:
                physical[n] = s.get('name', f'Station {n}')
    registry = []
    for num in sorted(physical):
        prev = preserved.get(num, {})
        registry.append({
            'number': num,
            'zone_name': prev.get('zone_name', physical[num]),
            'last_verified': prev.get('last_verified', ''),
            'notes': prev.get('notes', ''),
            'checklist': prev.get('checklist', [dict(c) for c in DEFAULT_CHECK]),
        })
    return registry


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def parse_days(s):
    if not s:
        return []
    parts = [p.strip() for p in re.split(r'[;,]', s) if p.strip()]
    return parts


def parse_budget(s):
    if not s:
        return 100
    m = re.search(r'(\d+)', s)
    return int(m.group(1)) if m else 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv_path')
    ap.add_argument('--out', default='data/controllers.json')
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv_path)))
    if not rows:
        print('No rows found', file=sys.stderr)
        sys.exit(1)

    preserved = load_existing_station_registry(args.out)

    # Group: controller -> program -> { meta, start_times: set, stations: ordered list w/ duration per (start_time, station_number) }
    # Important: duration can theoretically vary across start_times of the same program, but in practice K-Rain shows one duration per (program, station). We'll verify.
    controllers = {}

    for r in rows:
        ctl_name = r['module'].strip()
        ctl_id = slugify(ctl_name)
        prog_name = r['program'].strip()
        prog_id = f"{ctl_id}__{slugify(prog_name)}"
        start_time = r['start_time'].strip()
        station_num = int(r['station_number'])
        station_name = r['station_name'].strip()
        try:
            dur = int(r['duration_total_mins'])
        except (ValueError, KeyError):
            dur = int(r.get('duration_minutes', 0)) + 60 * int(r.get('duration_hours', 0))

        if ctl_id not in controllers:
            controllers[ctl_id] = {
                'id': ctl_id,
                'name': ctl_name,
                'type': 'krain',
                'programs': {}
            }
        ctl = controllers[ctl_id]

        if prog_id not in ctl['programs']:
            ctl['programs'][prog_id] = {
                'id': prog_id,
                'name': prog_name,
                'calendar': r.get('calendar', 'Custom').strip() or 'Custom',
                'days': parse_days(r.get('days', '')),
                'water_budget': parse_budget(r.get('water_budget', '100')),
                'start_times': set(),
                # station_durations: { station_num: { 'name': ..., 'durations': set of (start_time, dur) } }
                '_stations_obs': defaultdict(lambda: {'name': None, 'observations': []}),
            }
        prog = ctl['programs'][prog_id]
        prog['start_times'].add(start_time)
        prog['_stations_obs'][station_num]['name'] = station_name
        prog['_stations_obs'][station_num]['observations'].append((start_time, dur))

    # Finalize: collapse station observations into single duration per station.
    # If durations differ across start_times for same station, warn and use the max (most permissive).
    for ctl in controllers.values():
        for prog in ctl['programs'].values():
            stations = []
            for num in sorted(prog['_stations_obs'].keys()):
                obs = prog['_stations_obs'][num]
                durs = {d for _, d in obs['observations']}
                if len(durs) > 1:
                    print(f"  WARN: {prog['id']} station {num} has varying durations across start times: {durs}. Using max.", file=sys.stderr)
                stations.append({
                    'number': num,
                    'name': obs['name'],
                    'duration_min': max(durs),
                })
            prog['stations'] = stations
            prog['start_times'] = sorted(prog['start_times'])
            del prog['_stations_obs']
        ctl['programs'] = sorted(ctl['programs'].values(), key=lambda p: p['name'])
        ctl['stations'] = build_station_registry(ctl['programs'], preserved.get(ctl['id'], {}))

    output = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'source': f'K-Rain dashboard via Gemini agent ({Path(args.csv_path).name})',
        'controllers': sorted(controllers.values(), key=lambda c: c['name']),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {len(output['controllers'])} controllers, "
          f"{sum(len(c['programs']) for c in output['controllers'])} programs to {out_path}")


if __name__ == '__main__':
    main()
