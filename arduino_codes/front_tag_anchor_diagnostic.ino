#include <DW1000Jang.hpp>
#include <DW1000JangRTLS.hpp>

const uint8_t PIN_SS = 10;
const uint8_t PIN_RST = 7;

const uint16_t DEVICE_ADDRESS = 5;
const int ROBOT_TAG_ID = 2;

device_configuration_t DEFAULT_CONFIG = {
    false, true, true, true, false,
    SFDMode::STANDARD_SFD,
    Channel::CHANNEL_5,
    DataRate::RATE_850KBPS,
    PulseFrequency::FREQ_16MHZ,
    PreambleLength::LEN_256,
    PreambleCode::CODE_3
};

frame_filtering_configuration_t TAG_FRAME_FILTER_CONFIG = {
    false, false, true, false, false, false, false, false
};

void printResult(int anchorId, New_structure result) {
    Serial.print("TAG,");
    Serial.print(ROBOT_TAG_ID);
    Serial.print(",A");
    Serial.print(anchorId);
    Serial.print(",");

    if (result.success) {
        Serial.print("OK,");
        Serial.println(result.distance, 3);
    } else {
        Serial.println("FAIL");
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("ROBOT_FRONT_TAG_ANCHOR_DIAGNOSTIC_READY");

    DW1000Jang::initializeNoInterrupt(PIN_SS, PIN_RST);
    DW1000Jang::applyConfiguration(DEFAULT_CONFIG);
    DW1000Jang::enableFrameFiltering(TAG_FRAME_FILTER_CONFIG);

    DW1000Jang::setDeviceAddress(DEVICE_ADDRESS);
    DW1000Jang::setNetworkId(RTLS_APP_ID);
    DW1000Jang::setAntennaDelay(16436);

    DW1000Jang::setPreambleDetectionTimeout(64);
    DW1000Jang::setSfdDetectionTimeout(273);
    DW1000Jang::setReceiveFrameWaitTimeoutPeriod(5000);
}

void loop() {
    New_structure res1 = DW1000JangRTLS::Tag_Distance_Request(1, 1500);
    printResult(1, res1);
    delay(50);

    New_structure res2 = DW1000JangRTLS::Tag_Distance_Request(2, 1500);
    printResult(2, res2);
    delay(50);

    New_structure res3 = DW1000JangRTLS::Tag_Distance_Request(3, 1500);
    printResult(3, res3);
    delay(250);
}
