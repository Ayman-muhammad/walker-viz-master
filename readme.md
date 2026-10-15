# walker-viz

Real-time visualization of a TienKung (TG2) robot's joint state in RViz, running inside Docker.

The robot publishes raw motor status over ROS 2 (DDS). This project picks those messages up, converts them into standard `JointState` messages, and feeds them through the robot's URDF so RViz shows the robot moving live.

## How it fits together

```
TienKung robot ──DDS──> relay.py ──/tg2_joints──> joint_state_publisher ──/joint_states──> robot_state_publisher ──/tf──> RViz2
 (bodyctrl_msgs)        (motor ID -> joint name)    (merges + re-publishes at 50 Hz)         (URDF -> TF tree)
```

1. **Robot** publishes motor status on `/arm/status`, `/leg/status`, `/waist/status` and `/head/status` using `bodyctrl_msgs/MotorStatusMsg`.
2. **`relay.py`** subscribes to those topics, maps each numeric motor ID to a URDF joint name, and publishes a `sensor_msgs/JointState` on `/tg2_joints` at 50 Hz.
3. **`joint_state_publisher`** reads `/tg2_joints` and publishes the combined `/joint_states`.
4. **`robot_state_publisher`** loads the URDF and turns joint states into the TF tree.
5. **RViz2** renders the robot model from the TF tree.

## What `bodyctrl_msgs` is

The robot's custom message package. It defines `MotorStatusMsg`, the format in which the robot reports each motor's position, keyed by motor ID. Without it, the container cannot deserialize anything the robot sends. It is built from the local `msgs/` folder.

## What the Dockerfile does

Two-stage build on ROS 2 Humble (`ros-core`):

**Build stage**
- Installs build tools, `colcon`, `rosdep`, `xacro` and Fast DDS (`rmw_fastrtps_cpp`).
- Clones the robot description from [Open-X-Humanoid/Tienkung_URDF](https://github.com/Open-X-Humanoid/Tienkung_URDF) into `/ros2_ws/src`.
- Copies `msgs/` (containing `bodyctrl_msgs`) into the same workspace.
- Resolves dependencies with `rosdep` and builds `bodyctrl_msgs` and `tiangong2pro_urdf` with `colcon`.

**Runtime stage**
- Installs only what is needed to run: `rviz2`, `robot_state_publisher`, `joint_state_publisher_gui` (which also provides `joint_state_publisher`), `xacro` and Fast DDS.
- Copies the built workspace (`/ros2_ws`), `fastdds.xml` and `relay.py` from the build stage and the build context.
- Sets the DDS environment: `FASTRTPS_DEFAULT_PROFILES_FILE=/root/fastdds.xml`, shared memory transport disabled (`RMW_FASTRTPS_USE_SHM=0`), `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, `ROS_DOMAIN_ID=0`.
- Adds ROS and workspace sourcing to `/root/.bashrc`, so every new shell is ready to use (`tg2.bashrc` holds the same two lines).

## Other files

| File | Purpose |
|---|---|
| `fastdds.xml` | Fast DDS profile. Sets the robot (`Host ip addr`) as an initial discovery peer so the container finds it over UDP unicast. Edit the address if your robot's IP differs. |
| `relay.py` | Motor status to `JointState` relay (see above). |
| `tg2.bashrc` | The ROS sourcing lines, for reference. |

## Build

From the project directory (needs `Dockerfile`, `fastdds.xml`, `relay.py` and `msgs/`):

```bash
sudo docker build -t walker-viz:v2 .
```

## Run

Start the container (this example is for WSLg on Windows). Replace `<container-name>` with any name you like:

```bash
sudo docker run -dit --rm --name <container-name> --net=host \
  -e DISPLAY="${DISPLAY:-:0}" \
  -e WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" \
  -e XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}" \
  -v /mnt/wslg/.X11-unix:/tmp/.X11-unix \
  -v /mnt/wslg:/mnt/wsl \
  -v $HOME/walker-viz/relay.py:/root/relay.py \
  walker-viz:v2
```

`--net=host` is required so the container can reach the robot over the network. The `relay.py` mount is optional; it lets you edit the relay on the host without rebuilding.

## Start the pipeline

The pipeline needs **four terminals, all inside the same container**. Open each one with:

```bash
sudo docker exec -it <container-name> bash
```

Then run one command per terminal:

**1. Relay**
```bash
python3 /root/relay.py
```

**2. Robot state publisher**
```bash
ros2 run robot_state_publisher robot_state_publisher --ros-args \
  -p robot_description:="$(cat <path-to-urdf>)"
```
`<path-to-urdf>` is the URDF file inside the cloned `Tienkung_URDF` package under `/ros2_ws/src/`.

**3. Joint state publisher**
```bash
ros2 run joint_state_publisher joint_state_publisher --ros-args \
  -p source_list:="['/tg2_joints']" -p rate:=50
```

**4. RViz**
```bash
rviz2
```

In RViz, set the **Fixed Frame** to `pelvis` (the robot's base frame) and add a **RobotModel** display (description topic `/robot_description`).

## Known limitations

- **Ankle mapping is a best guess.** Each ankle is driven by two motors through a parallel linkage. `relay.py` assumes `pitch = (a+b)/2`, `roll = (a-b)/2` (`ANKLE_MODE = "parallel"`). Verify on the robot and adjust `ANKLE_MODE` and the sign tables if the ankles look wrong.
- All joint signs default to `+1`. Flip entries in `SIGN` if any joint moves in the wrong direction.