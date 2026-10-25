# 桌面物品视觉夹取程序

本仓库整理本次任务使用的视觉、机械臂、夹爪及联动程序，原工作区代码与配置保持原位且未改动。

## 目录

| 路径 | 内容 |
| --- | --- |
| t/ | 联动入口、角度边界测试、记录核对程序 |
| camera/ | 实时采集、候选点、手眼坐标链与法兰目标计算 |
| estun/ | 分段控制、反馈桥、Windows反馈转发、ROS消息源码 |
| jia/ros2_ws/src/ | 夹爪串口驱动、协议、服务与ROS接口 |
| try/ | 一次运动到位并闭合夹爪的原控制程序 |
| third_party/orbbec_ws/src/OrbbecSDK_ROS2 | 官方相机驱动固定版本子模块 |
| docs/sequence.md | 完整顺序逻辑图 |

发布副本中的现场IP与USB设备序列号已替换为文档示例值；实际标定、图像、深度、设备反馈和现场日志留在本机，没有上传。t/capture/frame_records.json 是合成角度边界测试夹具，并非实机观测。具体改动及文件哈希见 SOURCE_MANIFEST.json。

角度边界修正采用时间顺序展开欧拉角；位置计算、视觉选点、静止阈值、目标姿态、夹爪偏移及控制参数沿用实验版本。发布整理仅替换现场标识、移除现场数据并添加构建说明，不改变这些算法与参数。

## 获取与构建

环境：Ubuntu22.04 / WSL2、ROS2 Humble、Python3.10。官方相机驱动及系统依赖见 dependencies.lock.json。

```bash
git clone --recurse-submodules https://github.com/acowopenmarket/shiyan1.git
cd shiyan1
source /opt/ros/humble/setup.bash
sudo apt install python3-numpy python3-opencv python3-yaml python3-serial \
  python3-colcon-common-extensions ros-humble-cv-bridge \
  ros-humble-message-filters ros-humble-trajectory-msgs ros-humble-std-srvs
(cd estun/ros2_ws && colcon build --symlink-install)
(cd jia/ros2_ws && colcon build --symlink-install \
  --build-base build_wsl --install-base install_wsl)
export ORBBEC_WS="$PWD/third_party/orbbec_ws"
# 按官方相机README安装系统依赖后构建；不启动设备。
(cd "$ORBBEC_WS" && colcon build --symlink-install \
  --parallel-workers 2 --cmake-args -DCMAKE_BUILD_TYPE=Release)
```

已有相机工作空间时，可将 ORBBEC_WS 指向该工作空间。

## 离线验证

```bash
bash scripts/verify_offline.sh
```

覆盖角度边界、视觉和坐标链、机械臂数学与本机回环协议、夹取流程、夹爪协议及客户端；不启动实机。验证记录在 docs/ 中。

## 本地配置后运行

保留原有同级目录，使用独立副本配置真实现场参数。先将本地真实标定放入 camera/results/handeye_real_20261023/calibration.json（该目录被Git忽略，不能使用虚构标定）。将程序中的文档示例IP与 REPLACE_WITH_LOCAL_SERIAL 替换为自己的现场值，确认与设备安装及网络匹配。

Windows按 estun/windows_feedback_relay.py 的参数启动只读反馈转发器。WSL设置实际 ORBBEC_WS、接入相机与夹爪USB，并在仓库根目录使用：

```bash
bash t/run_experiment.sh              # 仅实时采集和计算
bash t/run_experiment.sh --execute    # 实时检查通过后执行一次动作流程
```

执行流程为调姿态 → XY → Z → 闭合一次，没有自动开爪、抬升、返回或动作重发。错误即停止后续发送，软件退出不能保证停止控制器已经接收的动作。设备动作完成不能单独证明物体实际夹持。

记录核对程序 t/summarize_experiment.py 使用本地运行日志；本次真实日志没有公开，需要在本地提供对应记录后使用。

## 第三方来源

官方相机驱动通过子模块固定本次使用版本，保留原许可证。夹爪包、ROS消息及官方代码对照保留原作者和许可证元数据；见 estun/estun_ros2_control/THIRD_PARTY.md。本仓库不改变原代码授权范围。
