"""Acquire one fresh burst, call existing algorithm unchanged, print read-only components."""
import argparse
from collections import deque
import os,signal,subprocess,time
from pathlib import Path
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import Image,CameraInfo
from codroid_msgs.msg import RobotInfo
from cv_bridge import CvBridge
from configs import load,save,DEFAULT_CONFIG,PROJECT_ROOT
from handeye_calibration.capture import stamp,camera_profile
from vision_center.grasp_candidate import aligned_profiles
from coordinate_transform.pose_ranges import pose_component_ranges

p=argparse.ArgumentParser(); p.add_argument('--output',required=True)
args=p.parse_args(); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
children=[]; logs=[]; node=None; captured=False
try:
    commands=[('camera',['bash',str(PROJECT_ROOT/'scripts/run_camera.sh')]),
              ('feedback',['ros2','run','estun_segmented','bridge','--receive-only',
                           '--controller-ip','192.0.2.100','--feedback-source-ip','198.51.100.1'])]
    for name,command in commands:
        log=(out/(name+'.log')).open('w'); logs.append(log)
        children.append(subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True))
    rclpy.init(); node=Node('current_candidate_snapshot_readonly'); bridge=CvBridge()
    keys=['color','depth','ci','di','robot']; buffers={k:deque(maxlen=80) for k in keys}
    subs=[]
    for k,typ,topic in [('color',Image,'/camera/color/image_raw'),('depth',Image,'/camera/depth/image_raw'),
                       ('ci',CameraInfo,'/camera/color/camera_info'),('di',CameraInfo,'/camera/depth/camera_info'),
                       ('robot',RobotInfo,'/RobotInfo')]:
        subs.append(node.create_subscription(typ,topic,lambda m,k=k:buffers[k].append((m,time.monotonic())),QoSProfile(depth=30)))
    start=time.monotonic(); frames=[]; poses=[]; seen=set(); records=[]
    while time.monotonic()-start<45:
        rclpy.spin_once(node,timeout_sec=.1)
        if time.monotonic()-start<8 or not all(buffers.values()): continue
        image,arrival=buffers['color'][-1]
        pairs={k:min(buffers[k],key=lambda pair:abs(stamp(pair[0])-stamp(image))) for k in keys[1:]}
        messages=[image]+[pair[0] for pair in pairs.values()]
        span=max(map(stamp,messages))-min(map(stamp,messages))
        if span>.05 or time.monotonic()-arrival>.5: continue
        depth,ci,di,robot=[pairs[k][0] for k in ['depth','ci','di','robot']]
        if (len({m.header.frame_id for m in [image,depth,ci,di]})!=1 or
                len({(m.width,m.height) for m in [image,depth,ci,di]})!=1 or
                not aligned_profiles(camera_profile(ci),camera_profile(di))): continue
        if stamp(image) in seen: continue
        if int(robot.fault_flag)!=0: raise ValueError('ROBOT_FEEDBACK_FAULT')
        seen.add(stamp(image)); frames.append(bridge.imgmsg_to_cv2(depth,'passthrough').copy())
        poses.append(list(robot.end_positions))
        records.append(dict(image_stamp=stamp(image),depth_stamp=stamp(depth),robot_stamp=stamp(robot),
                            sync_span_sec=span,robot_pose=list(robot.end_positions),
                            color_camera_info=camera_profile(ci),depth_camera_info=camera_profile(di)))
        if len(frames)<15: continue
        np.save(out/'depth_series.npy',np.stack(frames))
        cv2.imwrite(str(out/'color.png'),bridge.imgmsg_to_cv2(image,'bgr8'))
        context=dict(camera_frame=image.header.frame_id,camera_info=camera_profile(ci),
            depth_camera_info=camera_profile(di),image_stamp=stamp(image),robot_stamp=stamp(robot),
            robot_pose_at_capture=list(robot.end_positions),robot_fault=int(robot.fault_flag),robot_state=robot.state,
            depth_encoding=depth.encoding,capture_sync_error_sec=max(r['sync_span_sec'] for r in records),
            sample_count=len(frames),robot_pose_component_ranges=pose_component_ranges(poses),
            robot_pose_component_ranges_raw=np.ptp(poses,axis=0).tolist(),
            angle_range_method='continuous_euler_unwrap_2pi',
            data_kind='current_single_object_readonly_burst',motion_sent=False)
        save(out/'snapshot.json',context); save(out/'depth_info.json',camera_profile(di))
        save(out/'frame_records.json',records); captured=True; print('CAPTURED '+str(out),flush=True); break
    if not captured:
        save(out/'capture_failure.json',dict(success=False,reason='NO_SYNCHRONIZED_BURST',
                                           counts={k:len(v) for k,v in buffers.items()},motion_sent=False))
        raise ValueError('NO_SYNCHRONIZED_BURST')
finally:
    if node: node.destroy_node()
    if rclpy.ok(): rclpy.shutdown()
    for child in reversed(children):
        try: os.killpg(child.pid,signal.SIGINT)
        except ProcessLookupError: pass
        try: child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try: os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            child.wait(timeout=5)
    for log in logs: log.close()

# Call the existing candidate CLI and existing compensation function, unchanged.
command=['python3','-m','vision_center.candidate_cli','--snapshot',str(out/'snapshot.json'),
    '--depth-series',str(out/'depth_series.npy'),'--image',str(out/'color.png'),
    '--depth-info',str(out/'depth_info.json'),'--calibration',
    str(PROJECT_ROOT/'results/handeye_real_20261023/calibration.json'),'--output',str(out/'computed')]
completed=subprocess.run(command,cwd=PROJECT_ROOT)
if completed.returncode: raise SystemExit(completed.returncode)
from coordinate_transform.geometry import RobotConvention,target_components
measurement=load(out/'computed/measurement.json'); cfg=load(DEFAULT_CONFIG)
grasp=load(PROJECT_ROOT/'configs/grasp_down.example.json')
target=target_components(measurement['point_base_m'],grasp['grasp_rpy_rad'],RobotConvention(),
                         cfg['flange_to_gripper_m'],grasp['grasp_rpy_rad'],cfg['min_flange_z_m'])
target.update(input_point_kind=measurement['point_kind'],input_point_base_m=measurement['point_base_m'],
              source=str(out/'computed/measurement.json'),eligible_for_motion_review=False,
              gripper_offset_physically_verified=cfg['gripper_offset_physically_verified'])
save(out/'robotmove_components.json',target)
print('EXISTING PROGRAM OUTPUT:',target['flange_pose'],flush=True)
