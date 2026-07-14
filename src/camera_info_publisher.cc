#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <camera_info_manager/camera_info_manager.hpp>

using namespace std::placeholders;

// Publishes CameraInfo alongside a camera's image_raw stream, loading
// per-camera intrinsics/distortion from a calibration YAML via
// camera_info_manager. Runs as a separate node/executable so it can be
// paired with any image_raw publisher without touching the capture loop.
class CameraInfoPublisher : public rclcpp::Node
{
public:
    CameraInfoPublisher()
    : Node("camera_info_publisher")
    {
        declare_parameter("camera_name", "camera");
        declare_parameter("camera_info_url", "");
        declare_parameter("image_topic", "image_raw");
        declare_parameter("camera_info_topic", "camera_info");

        camera_name_ = get_parameter("camera_name").as_string();
        camera_info_url_ = get_parameter("camera_info_url").as_string();
        image_topic_ = get_parameter("image_topic").as_string();
        camera_info_topic_ = get_parameter("camera_info_topic").as_string();

        camera_info_manager_ = std::make_shared<camera_info_manager::CameraInfoManager>(
            this, camera_name_, camera_info_url_);

        if (!camera_info_manager_->isCalibrated()) {
            RCLCPP_WARN(
                get_logger(),
                "No valid calibration found for camera '%s' at '%s' - publishing uncalibrated CameraInfo",
                camera_name_.c_str(), camera_info_url_.c_str());
        }

        camera_info_pub_ = create_publisher<sensor_msgs::msg::CameraInfo>(camera_info_topic_, 10);

        image_sub_ = create_subscription<sensor_msgs::msg::Image>(
            image_topic_, rclcpp::SensorDataQoS(),
            std::bind(&CameraInfoPublisher::image_callback, this, _1));
    }

private:
    void image_callback(const sensor_msgs::msg::Image::ConstSharedPtr msg)
    {
        // Stamp CameraInfo with the incoming image's header so downstream
        // time-synchronizers (image_proc, stereo_image_proc) can pair them.
        sensor_msgs::msg::CameraInfo info = camera_info_manager_->getCameraInfo();
        info.header = msg->header;
        camera_info_pub_->publish(info);
    }

    std::string camera_name_, camera_info_url_, image_topic_, camera_info_topic_;
    std::shared_ptr<camera_info_manager::CameraInfoManager> camera_info_manager_;
    rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr camera_info_pub_;
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr image_sub_;
};

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<CameraInfoPublisher>());
    rclcpp::shutdown();
    return 0;
}
