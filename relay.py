#!/usr/bin/env python3
"""Relay TienKung motor status -> sensor_msgs/JointState on /tg2_joints."""
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from bodyctrl_msgs.msg import MotorStatusMsg

ARM_JOINTS = ["shoulder_pitch", "shoulder_roll", "shoulder_yaw",
              "elbow_pitch", "elbow_yaw", "wrist_pitch", "wrist_roll"]

MOTOR_TO_JOINT = {}
for i, j in enumerate(ARM_JOINTS):
    MOTOR_TO_JOINT[11 + i] = f"{j}_l_joint"
    MOTOR_TO_JOINT[21 + i] = f"{j}_r_joint"

MOTOR_TO_JOINT[31] = "body_yaw_joint"

MOTOR_TO_JOINT[1] = "head_yaw_joint"
MOTOR_TO_JOINT[2] = "head_pitch_joint"
MOTOR_TO_JOINT[3] = "head_roll_joint"

LEG_JOINTS = ["hip_roll", "hip_pitch", "hip_yaw", "knee_pitch"]
for i, j in enumerate(LEG_JOINTS):
    MOTOR_TO_JOINT[51 + i] = f"{j}_l_joint"
    MOTOR_TO_JOINT[61 + i] = f"{j}_r_joint"

SIGN = {mid: 1.0 for mid in MOTOR_TO_JOINT}

# Ankle: two motors per side drive pitch+roll through a parallel linkage.
# "parallel": pitch=(a+b)/2, roll=(a-b)/2   (BEST GUESS - verify on the robot)
# "direct":   a -> pitch, b -> roll
ANKLE_MODE = "parallel"
ANKLES = {"l": (55, 56), "r": (65, 66)}
ANKLE_ROLL_SIGN = {"l": 1.0, "r": 1.0}
ANKLE_PITCH_SIGN = {"l": 1.0, "r": 1.0}

STATUS_TOPICS = ["/arm/status", "/leg/status", "/waist/status", "/head/status"]


class Relay(Node):
    def __init__(self):
        super().__init__("tg2_joint_relay")
        self.pos = {}
        self.ankle_raw = {}
        self.pub = self.create_publisher(JointState, "/tg2_joints", 10)
        for topic in STATUS_TOPICS:
            self.create_subscription(
                MotorStatusMsg, topic, self.on_status, qos_profile_sensor_data)
        self.create_timer(1.0 / 50.0, self.publish)
        self.get_logger().info(
            f"relaying {STATUS_TOPICS} -> /tg2_joints (ankle mode: {ANKLE_MODE})")

    def on_status(self, msg):
        for s in msg.status:
            mid = int(s.name)
            if mid in MOTOR_TO_JOINT:
                self.pos[MOTOR_TO_JOINT[mid]] = SIGN[mid] * float(s.pos)
            else:
                self.ankle_raw[mid] = float(s.pos)

    def publish(self):
        names = list(self.pos.keys())
        vals = list(self.pos.values())
        for side, (a, b) in ANKLES.items():
            if a in self.ankle_raw and b in self.ankle_raw:
                ra, rb = self.ankle_raw[a], self.ankle_raw[b]
                if ANKLE_MODE == "parallel":
                    pitch, roll = (ra + rb) / 2.0, (ra - rb) / 2.0
                else:
                    pitch, roll = ra, rb
                names += [f"ankle_pitch_{side}_joint", f"ankle_roll_{side}_joint"]
                vals += [ANKLE_PITCH_SIGN[side] * pitch,
                         ANKLE_ROLL_SIGN[side] * roll]
        if not names:
            return
        out = JointState()
        out.header.stamp = self.get_clock().now().to_msg()
        out.name = names
        out.position = vals
        self.pub.publish(out)


def main():
    rclpy.init()
    node = Relay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()