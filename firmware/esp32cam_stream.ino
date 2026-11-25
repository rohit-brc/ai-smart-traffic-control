// Minimal local MJPEG stream for an AI Thinker ESP32-CAM.
// Add your Wi-Fi credentials locally before flashing. Do not commit real credentials.
#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// AI Thinker ESP32-CAM pin map.
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

static esp_err_t stream_handler(httpd_req_t* request) {
  static const char* boundary = "frame";
  esp_err_t result = httpd_resp_set_type(request, "multipart/x-mixed-replace;boundary=frame");
  if (result != ESP_OK) return result;

  while (true) {
    camera_fb_t* frame = esp_camera_fb_get();
    if (!frame) return ESP_FAIL;
    char header[96];
    int header_length = snprintf(header, sizeof(header),
      "--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
      boundary, static_cast<unsigned>(frame->len));
    result = httpd_resp_send_chunk(request, header, header_length);
    if (result == ESP_OK) result = httpd_resp_send_chunk(request,
      reinterpret_cast<const char*>(frame->buf), frame->len);
    if (result == ESP_OK) result = httpd_resp_send_chunk(request, "\r\n", 2);
    esp_camera_fb_return(frame);
    if (result != ESP_OK) break;
  }
  return result;
}

static void start_stream_server() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;
  httpd_handle_t server = nullptr;
  if (httpd_start(&server, &config) == ESP_OK) {
    httpd_uri_t route = {};
    route.uri = "/stream";
    route.method = HTTP_GET;
    route.handler = stream_handler;
    httpd_register_uri_handler(server, &route);
  }
}

void setup() {
  Serial.begin(115200);
  camera_config_t camera = {};
  camera.ledc_channel = LEDC_CHANNEL_0;
  camera.ledc_timer = LEDC_TIMER_0;
  camera.pin_d0 = Y2_GPIO_NUM; camera.pin_d1 = Y3_GPIO_NUM;
  camera.pin_d2 = Y4_GPIO_NUM; camera.pin_d3 = Y5_GPIO_NUM;
  camera.pin_d4 = Y6_GPIO_NUM; camera.pin_d5 = Y7_GPIO_NUM;
  camera.pin_d6 = Y8_GPIO_NUM; camera.pin_d7 = Y9_GPIO_NUM;
  camera.pin_xclk = XCLK_GPIO_NUM; camera.pin_pclk = PCLK_GPIO_NUM;
  camera.pin_vsync = VSYNC_GPIO_NUM; camera.pin_href = HREF_GPIO_NUM;
  camera.pin_sccb_sda = SIOD_GPIO_NUM; camera.pin_sccb_scl = SIOC_GPIO_NUM;
  camera.pin_pwdn = PWDN_GPIO_NUM; camera.pin_reset = RESET_GPIO_NUM;
  camera.xclk_freq_hz = 20000000;
  camera.pixel_format = PIXFORMAT_JPEG;
  camera.frame_size = FRAMESIZE_VGA;
  camera.jpeg_quality = 12;
  camera.fb_count = 2;
  if (esp_camera_init(&camera) != ESP_OK) {
    Serial.println("Camera initialization failed");
    return;
  }

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.printf("\nStream: http://%s:81/stream\n", WiFi.localIP().toString().c_str());
  start_stream_server();
}

void loop() { delay(1000); }
