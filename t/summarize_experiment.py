"""Summarize recorded evidence only; no device access."""
from datetime import datetime
import json
from pathlib import Path
import yaml

run = Path(__file__).resolve().parent / 'run_20261025_181148_327'
events = [json.loads(line) for line in (run / 'pick.log').read_text().splitlines()
          if line.startswith('{')]
close = [e for e in events if e['event'] == 'GRIPPER_CLOSE_SENT']
sent = [e for e in events if e['event'] == 'SEND']
arrived = [e for e in events if e['event'] == 'ARRIVED']
pick_arrived = next(e for e in events if e['event'] == 'PICK_ARRIVED')
close_stamp = datetime.strptime(close[0]['time'], '%Y-%m-%dT%H:%M:%S%z').timestamp()
states = [s for s in yaml.safe_load_all((run / 'gripper_state.log').read_text()) if s]
post = [s for s in states if s['header']['stamp']['sec'] +
        s['header']['stamp']['nanosec'] * 1e-9 >= close_stamp + 1]
assert len(sent) == len(arrived) == 3 and len(close) == 1
assert not any(e['event'] == 'PICK_ABORT' for e in events)
assert len(post) >= 3
assert all(s['target_reached'] and s['raw_speed'] == 0 for s in post[-3:])
assert all(e.get('fault_flag', 0) == 0 for e in events)
summary = dict(
    phase_sequence=[e['stage'] for e in sent], motion_commands=len(sent),
    arrived_phases=len(arrived), close_commands=len(close), aborts=0,
    final_position_error_m=pick_arrived['position_error_m'],
    final_angle_error_rad=pick_arrived['angle_error_rad'],
    gripper_last_three_stationary_and_target_reached=True,
    gripper_last_motor_angle_deg=post[-1]['motor_angle_deg'],
    z_clamped=json.loads((run / 'capture/robotmove_components.json').read_text())['z_clamped'],
    object_held_verified=False,
    scope='Robot arrival and gripper motor feedback only; no object-holding sensor evidence',
)
(run / 'evidence_summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
