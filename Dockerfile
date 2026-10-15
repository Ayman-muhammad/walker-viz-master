FROM ghcr.io/sloretz/ros:humble-ros-core AS build_stage
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y \
    build-essential cmake git \
    python3-colcon-common-extensions python3-rosdep \
    ros-humble-rmw-fastrtps-cpp \
    ros-humble-xacro \
    libyaml-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws/src
RUN git clone https://github.com/Open-X-Humanoid/Tienkung_URDF.git
COPY msgs/ /ros2_ws/src/msgs/

WORKDIR /ros2_ws
RUN source /opt/ros/humble/setup.bash && \
    (rosdep init || true) && rosdep update && \
    rosdep install --from-paths src --ignore-src -y --skip-keys "rospy roscpp" && \
    colcon build --packages-up-to bodyctrl_msgs tiangong2pro_urdf


#----------Runtime stage ---------
FROM ghcr.io/sloretz/ros:humble-ros-core
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y \
    ros-humble-rviz2 \
    ros-humble-robot-state-publisher \
    ros-humble-joint-state-publisher-gui \
    ros-humble-xacro \
    ros-humble-rmw-fastrtps-cpp \
    && rm -rf /var/lib/apt/lists/* 

COPY --from=build_stage /ros2_ws /ros2_ws
COPY fastdds.xml /root/fastdds.xml
COPY relay.py /root/relay.py

ENV FASTRTPS_DEFAULT_PROFILES_FILE=/root/fastdds.xml
ENV RMW_FASTRTPS_USE_SHM=0
ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ENV ROS_DOMAIN_ID=0
RUN echo "source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash" >> /root/.bashrc
CMD ["bash"]