#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <camera_info_manager/camera_info_manager.hpp>

using namespace std::placeholders;

// Publishes CameraInfo alongside a camera's image stream, loading per-camera
// intrinsics/distortion from a calibration YAML via camera_info_manager.
// Runs as a separate node/executable so it can be paired with any image
// publisher without touching the capture loop. Triggers off whichever
// message actually arrives -- the decoded sensor_msgs/Image on image_topic,
// or (when the paired dwe_ros2_parser has publish_compressed:=true, which
// stops publishing image_topic) the sensor_msgs/CompressedImage on
// "<image_topic>/compressed" instead, selected via use_compressed.
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
        declare_parameter("use_compressed", false);

        camera_name_ = get_parameter("camera_name").as_string();
        camera_info_url_ = get_parameter("camera_info_url").as_string();
        image_topic_ = get_parameter("image_topic").as_string();
        camera_info_topic_ = get_parameter("camera_info_topic").as_string();
        bool use_compressed = get_parameter("use_compressed").as_bool();

        camera_info_manager_ = std::make_shared<camera_info_manager::CameraInfoManager>(
            this, camera_name_, camera_info_url_);

        if (!camera_info_manager_->isCalibrated()) {
            RCLCPP_WARN(
                get_logger(),
                "No valid calibration found for camera '%s' at '%s' - publishing uncalibrated CameraInfo",
                camera_name_.c_str(), camera_info_url_.c_str());
        }

        camera_info_pub_ = create_publisher<sensor_msgs::msg::CameraInfo>(camera_info_topic_, 10);

        if (use_compressed) {
            compressed_sub_ = create_subscription<sensor_msgs::msg::CompressedImage>(
                image_topic_ + "/compressed", rclcpp::SensorDataQoS(),
                std::bind(&CameraInfoPublisher::compressed_callback, this, _1));
        } else {
            image_sub_ = create_subscription<sensor_msgs::msg::Image>(
                image_topic_, rclcpp::SensorDataQoS(),
                std::bind(&CameraInfoPublisher::image_callback, this, _1));
        }
    }

private:
    void image_callback(const sensor_msgs::msg::Image::ConstSharedPtr msg)
    {
        publish_info(msg->header);
    }

    void compressed_callback(const sensor_msgs::msg::CompressedImage::ConstSharedPtr msg)
    {
        publish_info(msg->header);
    }

    void publish_info(const std_msgs::msg::Header & header)
    {
        // Stamp CameraInfo with the incoming image's header so downstream
        // time-synchronizers (image_proc, stereo_image_proc) can pair them.
        sensor_msgs::msg::CameraInfo info = camera_info_manager_->getCameraInfo();
        info.header = header;
        camera_info_pub_->publish(info);
    }

    std::string camera_name_, camera_info_url_, image_topic_, camera_info_topic_;
    std::shared_ptr<camera_info_manager::CameraInfoManager> camera_info_manager_;
    rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr camera_info_pub_;
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr image_sub_;
    rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr compressed_sub_;
};

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<CameraInfoPublisher>());
    rclcpp::shutdown();
    return 0;
}
