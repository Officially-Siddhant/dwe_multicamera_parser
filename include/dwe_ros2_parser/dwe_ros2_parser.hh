#ifndef DWE_ROS2_PARSER_HH_
#define DWE_ROS2_PARSER_HH_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <opencv2/opencv.hpp>
#include <chrono>
#include <string>
#include "cv_bridge/cv_bridge.h"
#include <iostream>
#include <csignal>
#include <thread>
#include <atomic>
#include <filesystem>

using namespace std;

class DWE_Ros2_Parser : public rclcpp::Node {

    // Methods
    public:
        DWE_Ros2_Parser();
        ~DWE_Ros2_Parser();

    // Methods
    private:
        void fetch_ros_parameters();
        void dwe_loop();
        // (Re)open the capture device and apply all format/fps/exposure
        // settings. Called at startup and again by the stall watchdog.
        cv::VideoCapture open_camera();

    // Members
    private:

        // ROS2 Parameters
        string image_topic_, save_folder_, image_prefix_, frame_id_, device_path_;
        int width_, height_, framerate_, device_, exposure_;
        double stall_timeout_s_;
        bool auto_exposure_, show_image_, use_h264_, save_images_, publish_compressed_;

        // ROS2 variables
        rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr image_pub_;
        rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr compressed_pub_;

};

#endif