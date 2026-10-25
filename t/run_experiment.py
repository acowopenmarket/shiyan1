"""Wire existing capture, target calculation and pick programs; no target selection."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def existing_output(capture):
    measurement = read(capture / 'computed/measurement.json')
    if measurement.get('success') is not True:
        raise RuntimeError('Existing vision rejected capture: ' + measurement.get('reason', 'unknown'))
    target = read(capture / 'robotmove_components.json')
    if target.get('source') != str(capture / 'computed/measurement.json'):
        raise RuntimeError('Target does not reference this capture')
    # Copy the six components without changing position, height or orientation.
    return {'targets': {'视觉抓取点': target['flange_pose']}, 'motion': {}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--inspect-capture', type=Path,
                        help='Check a saved capture only; cannot execute with this option')
    args = parser.parse_args()
    if args.execute and args.inspect_capture:
        parser.error('Saved captures cannot be used for execution')
    if args.inspect_capture:
        capture = args.inspect_capture.resolve()
        try:
            config = existing_output(capture)
            print(json.dumps(config, ensure_ascii=False))
            return 0
        except (RuntimeError, OSError, KeyError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2

    run = ROOT / ('run_' + time.strftime('%Y%m%d_%H%M%S') + '_' + str(os.getpid()))
    run.mkdir()
    capture = run / 'capture'
    children, logs = [], []
    result = {'capture': str(capture), 'execute_requested': args.execute,
              'pick_started': False, 'success': False}
    try:
        with (run / 'capture.log').open('w') as log:
            completed = subprocess.run(
                [sys.executable, str(PROJECT / 'camera/local/current_candidate_snapshot.py'),
                 '--output', str(capture)], stdout=log, stderr=subprocess.STDOUT)
        # Inspect the reason even when the existing CLI exits nonzero.
        config = existing_output(capture)
        if completed.returncode:
            raise RuntimeError('Existing capture program exit: ' + str(completed.returncode))
        save(run / 'pick_targets.json', config)
        if not args.execute:
            result['success'] = True
            result['status'] = 'calculated_only'
            return 0
        # The snapshot program has stopped its own read-only bridge and camera.
        # Start exactly one existing motion bridge and one existing gripper node.
        commands = [
            ('bridge', ['ros2', 'run', 'estun_segmented', 'bridge',
                        '--feedback-source-ip', '198.51.100.1']),
            ('gripper', ['ros2', 'launch', 'ms42_gripper', 'gripper.launch.py',
                         'port:=/dev/serial/by-id/usb-1a86_USB_Single_Serial_REPLACE_WITH_LOCAL_SERIAL-if00',
                         'dry_run:=false']),
            ('gripper_state', ['ros2', 'topic', 'echo', '/ms42_gripper/state',
                               'ms42_gripper_interfaces/msg/GripperState']),
        ]
        for name, command in commands:
            log = (run / (name + '.log')).open('w')
            logs.append(log)
            children.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                             start_new_session=True))
        # Existing pick performs service readiness, feedback, start-pose and arrival gates.
        with (run / 'pick.log').open('w') as log:
            result['pick_started'] = True
            completed = subprocess.run(
                [sys.executable, str(PROJECT / 'try/run_pick.py'), '视觉抓取点',
                 '--config', str(run / 'pick_targets.json'), '--execute'],
                stdout=log, stderr=subprocess.STDOUT)
        result['pick_exit_code'] = completed.returncode
        result['success'] = completed.returncode == 0
        result['status'] = 'pick_program_completed' if result['success'] else 'pick_program_aborted'
        result['object_held_verified'] = False
        if result['success']:
            # Read-only recording after the one existing close command.
            time.sleep(3)
        return completed.returncode
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        result.update(status='aborted', reason=str(exc))
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        # No motion retries, automatic opening, lifting, or return movements.
        for child in reversed(children):
            if child.poll() is not None:
                continue
            os.killpg(child.pid, signal.SIGINT)
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=5)
        for log in logs:
            log.close()
        save(run / 'result.json', result)


if __name__ == '__main__':
    raise SystemExit(main())
