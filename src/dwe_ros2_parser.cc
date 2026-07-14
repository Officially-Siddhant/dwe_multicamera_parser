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

    // Configure publisher
    image_pub_ = create_publisher<sensor_msgs::msg::Image>(image_topic_, 1);

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

    // Fetch parameters
    device_ = get_parameter("device").as_int();
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
}

// Image Callback
void DWE_Ros2_Parser::dwe_loop() {

    // Create a video capture object
    cv::VideoCapture dwe_camera = cv::VideoCapture(device_, cv::CAP_V4L2); 

    // Choose compression. MJPG is FAST, H264 is more efficient but can bring latency
    int fourcc = cv::VideoWriter::fourcc('M', 'J', 'P', 'G'); 
    if (use_h264_) {
        fourcc = cv::VideoWriter::fourcc('H', '2', '6', '4');
    }
    dwe_camera.set(cv::CAP_PROP_FOURCC, fourcc);

    // These don't work properly
    dwe_camera.set(cv::CAP_PROP_FRAME_WIDTH, width_);
    dwe_camera.set(cv::CAP_PROP_FRAME_HEIGHT, height_);
    //dwe_camera.set(cv::CAP_PROP_FPS, framerate_);

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

    // Loop is run until Node is told to quit 
    while(running) {

        // Start time
        auto start = chrono::high_resolution_clock::now();

        // Retrive image        
        bool success = dwe_camera.read(image);

        // If image is received
        if (success) {

            // Shows image if set to true
            if (show_image_) {
                cv::imshow("DWE Camera", image);
                
                if (cv::waitKey(1) == 'q') {
                    break;
                }
            }

        // Publish image to ROS2
        cv_image.image = image;
        sensor_msgs::msg::Image image_msg = *cv_image.toImageMsg();
        image_msg.header.stamp = this->now();
        image_msg.header.frame_id = frame_id_;
        image_pub_->publish(image_msg);

        if (save_images_) {
            string filename = save_folder_ + "/" + image_prefix_ + to_string(image_msg.header.stamp.sec) + "." + to_string(image_msg.header.stamp.nanosec) + ".jpg";
            cv::imwrite(filename, image);
        }

    }
    }

    // Release camera object
    dwe_camera.release();
    cv::destroyAllWindows();

    // Exit node
    exit(0);
}
