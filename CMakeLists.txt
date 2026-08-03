cmake_minimum_required(VERSION 3.8)
project(auv_camera_bringup)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(image_transport REQUIRED)
find_package(OpenCV REQUIRED)
find_package(camera_info_manager REQUIRED)

# add exe
add_executable(dwe_ros2_parser src/main.cc src/dwe_ros2_parser.cc)
add_executable(image_sub src/image_subscriber.cc)
add_executable(camera_info_publisher src/camera_info_publisher.cc)

# include dirs
include_directories(include)

# install launch files, calibration configs, and udev rules (the latter for
# reference/copy -- colcon build has no privilege to install into /etc/udev
# itself, see udev/99-dwe-cameras.rules for manual install steps)
install(DIRECTORY
  launch
  config
  udev
  DESTINATION share/${PROJECT_NAME}
)

# add depend
ament_target_dependencies(dwe_ros2_parser
  rclcpp
  sensor_msgs
  cv_bridge
  image_transport
  OpenCV
)

ament_target_dependencies(image_sub
  rclcpp
  sensor_msgs
  cv_bridge
  image_transport
  OpenCV
)

ament_target_dependencies(camera_info_publisher
  rclcpp
  sensor_msgs
  camera_info_manager
)

# install targets
install(TARGETS
  dwe_ros2_parser
  image_sub
  camera_info_publisher
  DESTINATION lib/${PROJECT_NAME}
)


ament_package()