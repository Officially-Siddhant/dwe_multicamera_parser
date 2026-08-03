#include "dwe_ros2_parser/dwe_ros2_parser.hh"

// Node is running variable
atomic<bool> running(true);

// CTRL+C
void signal_handler(int signum) {
    running = false;
}
// Constructor
DWE_Ros2_Parser::DWE_Ros2_Parser() : Node("dwe_ros2_parser") {

    // Fetch ROS parameters
    fetch_ros_parameters();

    // Configure publisher(s). Both are created regardless of mode; only one
    // is actually published to per frame (see dwe_loop) based on
    // publish_compressed_.
    image_pub_ = create_publisher<sensor_msgs::msg::Image>(image_topic_, 1);
    compressed_pub_ = create_publisher<sensor_msgs::msg::CompressedImage>(
        image_topic_ + "/compressed", 1);

    // Start DWE Loop
    dwe_loop();

}

// Destructor
DWE_Ros2_Parser::~DWE_Ros2_Parser() {

}

// Fetch ROS parameters
void DWE_Ros2_Parser::fetch_ros_parameters() {

    // Get ROS parameter

    declare_parameter("device", 0);
    // Stable alternative to "device": a udev-symlinked path (e.g.
    // /dev/dwe_camera_left), immune to /dev/videoN index drift on USB
    // replug/re-enumeration. Takes priority over "device" when non-empty.
    declare_parameter("device_path", "");
    declare_parameter("image_topic", "/dwe/camera");
    declare_parameter("width", 1600);
    declare_parameter("height", 1200);
    declare_parameter("framerate", 60);
    declare_parameter("auto_exposure", false);
    declare_parameter("exposure", 100);
    declare_parameter("show_image", false);
    declare_parameter("use_h264", false);
    declare_parameter("save_images", false);
    declare_parameter("save_folder", " ~");
    declare_parameter("image_prefix", "image");
    declare_parameter("frame_id", "camera_frame");
    // Publish the raw encoded MJPEG bytes as sensor_msgs/CompressedImage on
    // "<image_topic>/compressed" instead of decoding every frame to BGR8.
    // The JPEG->BGR software decode (and publishing/recording a ~6x larger
    // uncompressed message) is what actually caps real-world fps well below
    // the configured framerate -- MJPG format alone does not. Requires
    // use_h264=false.
    declare_parameter("publish_compressed", false);

    // Fetch parameters
    device_ = get_parameter("device").as_int();
    device_path_ = get_parameter("device_path").as_string();
    image_topic_ = get_parameter("image_topic").as_string();
    width_ = get_parameter("width").as_int();
    height_ = get_parameter("height").as_int();
    framerate_ = get_parameter("framerate").as_int();
    auto_exposure_ = get_parameter("auto_exposure").as_bool();
    exposure_ = get_parameter("exposure").as_int();
    show_image_ = get_parameter("show_image").as_bool();
    use_h264_ = get_parameter("use_h264").as_bool();
    save_images_ = get_parameter("save_images").as_bool();
    save_folder_ = get_parameter("save_folder").as_string();
    image_prefix_ = get_parameter("image_prefix").as_string();
    frame_id_ = get_parameter("frame_id").as_string();
    publish_compressed_ = get_parameter("publish_compressed").as_bool();
}

// Image Callback
void DWE_Ros2_Parser::dwe_loop() {

    // Create a video capture object. Prefer the stable udev path when given;
    // fall back to the raw index (unstable across USB replug/reboot).
    cv::VideoCapture dwe_camera = device_path_.empty()
        ? cv::VideoCapture(device_, cv::CAP_V4L2)
        : cv::VideoCapture(device_path_, cv::CAP_V4L2);

    // Choose compression. MJPG is FAST, H264 is more efficient but can bring latency
    int fourcc = cv::VideoWriter::fourcc('M', 'J', 'P', 'G'); 
    if (use_h264_) {
        fourcc = cv::VideoWriter::fourcc('H', '2', '6', '4');
    }
    dwe_camera.set(cv::CAP_PROP_FOURCC, fourcc);

    if (publish_compressed_ && use_h264_) {
        RCLCPP_WARN(this->get_logger(),
                    "publish_compressed requires MJPG (use_h264=false); ignoring publish_compressed");
        publish_compressed_ = false;
    }
    if (publish_compressed_) {
        // Skip the backend's JPEG->BGR decode: read() then hands back the
        // raw encoded bytes (a 1-row CV_8UC1 Mat) instead of a decoded frame.
        dwe_camera.set(cv::CAP_PROP_CONVERT_RGB, 0);
    }

    // These don't work properly
    dwe_camera.set(cv::CAP_PROP_FRAME_WIDTH, width_);
    dwe_camera.set(cv::CAP_PROP_FRAME_HEIGHT, height_);

    // Enforce framerate. NOTE: configured_fps below is just the driver's
    // self-reported mode, not real throughput -- it can say 60 while actual
    // delivery is far lower. Trust the periodic "Measured capture rate" log
    // further down instead, which counts frames actually received.
    dwe_camera.set(cv::CAP_PROP_FPS, framerate_);
    double configured_fps = dwe_camera.get(cv::CAP_PROP_FPS);
    RCLCPP_INFO(this->get_logger(), "Requested %d fps, driver configured for %.1f fps",
                framerate_, configured_fps);

    // Set buffer to zero to not build up latency
    //dwe_camera.set(cv::CAP_PROP_BUFFERSIZE, 1);

    // Check if auto exposure should be disabled
    if (!auto_exposure_) {
        dwe_camera.set(cv::CAP_PROP_AUTO_EXPOSURE, 1);
        dwe_camera.set(cv::CAP_PROP_EXPOSURE, exposure_);
    }

    // Check if save dir exists, and if not create it 
    if (save_images_) {
    std::filesystem::path save_dir(save_folder_);
        if (!std::filesystem::exists(save_dir)) {
            std::filesystem::create_directory(save_dir);
        }
    }

    // Loop variables
    cv_bridge::CvImage cv_image;
    cv_image.encoding="bgr8";
    cv::Mat image;
    
    // Looks for interupts
    signal(SIGINT, signal_handler);

    // Measured (not driver-reported) capture rate: counts frames actually
    // delivered by read() and reports real fps every 5s. get(CAP_PROP_FPS)
    // above only reflects the configured mode, not what's really arriving --
    // this is the number to trust if it looks slower than requested.
    int frame_count = 0;
    auto fps_window_start = chrono::steady_clock::now();

    // Loop is run until Node is told to quit
    while(running) {

        // Retrive image
        bool success = dwe_camera.read(image);

        // If image is received
        if (success) {

            frame_count++;
            auto now_t = chrono::steady_clock::now();
            double elapsed = chrono::duration<double>(now_t - fps_window_start).count();
            if (elapsed >= 5.0) {
                RCLCPP_INFO(this->get_logger(), "Measured capture rate: %.1f fps",
                            frame_count / elapsed);
                frame_count = 0;
                fps_window_start = now_t;
            }

        // Publish image to ROS2. In compressed mode `image` holds the raw
        // encoded JPEG bytes (see CAP_PROP_CONVERT_RGB above); it is only
        // decoded to BGR below if show_image/save_images actually need it.
        builtin_interfaces::msg::Time stamp = this->now();
        cv::Mat decoded;

        if (publish_compressed_) {
            sensor_msgs::msg::CompressedImage compressed_msg;
            compressed_msg.header.stamp = stamp;
            compressed_msg.header.frame_id = frame_id_;
            compressed_msg.format = "jpeg";
            compressed_msg.data.assign(image.datastart, image.dataend);
            compressed_pub_->publish(compressed_msg);

            if (show_image_ || save_images_) {
                decoded = cv::imdecode(image, cv::IMREAD_COLOR);
            }
        } else {
            cv_image.image = image;
            sensor_msgs::msg::Image image_msg = *cv_image.toImageMsg();
            image_msg.header.stamp = stamp;
            image_msg.header.frame_id = frame_id_;
            image_pub_->publish(image_msg);
            decoded = image;
        }

        // Shows image if set to true
        if (show_image_ && !decoded.empty()) {
            cv::imshow("DWE Camera", decoded);

            if (cv::waitKey(1) == 'q') {
                break;
            }
        }

        if (save_images_ && !decoded.empty()) {
            string filename = save_folder_ + "/" + image_prefix_ + to_string(stamp.sec) + "." + to_string(stamp.nanosec) + ".jpg";
            cv::imwrite(filename, decoded);
        }

    }
    }

    // Release camera object
    dwe_camera.release();
    cv::destroyAllWindows();

    // Exit node
    exit(0);
}
