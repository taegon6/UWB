#include <DW1000Jang.hpp>
#include <DW1000JangUtils.hpp>
#include <DW1000JangRanging.hpp>
#include <DW1000JangRTLS.hpp>

#if defined(ESP8266)
const uint8_t PIN_SS = 15;
#else
const uint8_t PIN_RST = 7;
const uint8_t PIN_SS = 10;
#endif

// Change this to 1, 2, or 3 before uploading to each anchor.
const uint16_t DEVICE_ADDRESS = 1;

device_configuration_t DEFAULT_CONFIG = {
    false, true, true, true, false,
    SFDMode::STANDARD_SFD,
    Channel::CHANNEL_5,
    DataRate::RATE_850KBPS,
    PulseFrequency::FREQ_16MHZ,
    PreambleLength::LEN_256,
    PreambleCode::CODE_3
};

frame_filtering_configuration_t ANCHOR_FRAME_FILTER_CONFIG = {
    false, false, true, false, false, false, false, false
};

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.print("ANCHOR_READY,");
    Serial.println(DEVICE_ADDRESS);

#if defined(ESP8266)
    DW1000Jang::initializeNoInterrupt(PIN_SS);
#else
    DW1000Jang::initializeNoInterrupt(PIN_SS, PIN_RST);
#endif

    DW1000Jang::applyConfiguration(DEFAULT_CONFIG);
    DW1000Jang::enableFrameFiltering(ANCHOR_FRAME_FILTER_CONFIG);

    DW1000Jang::setPreambleDetectionTimeout(64);
    DW1000Jang::setSfdDetectionTimeout(273);
    DW1000Jang::setReceiveFrameWaitTimeoutPeriod(8000);

    DW1000Jang::setNetworkId(RTLS_APP_ID);
    DW1000Jang::setDeviceAddress(DEVICE_ADDRESS);
    DW1000Jang::setAntennaDelay(16436);
}

void loop() {
    DW1000JangRTLS::Anchor_Distance_Response();
}
