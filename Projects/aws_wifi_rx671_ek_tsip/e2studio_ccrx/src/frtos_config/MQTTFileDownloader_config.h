#ifndef MQTT_FILE_DOWNLOADER_CONFIG_H
#define MQTT_FILE_DOWNLOADER_CONFIG_H

#ifndef mqttFileDownloader_CONFIG_BLOCK_SIZE
#define mqttFileDownloader_CONFIG_BLOCK_SIZE        (16384U)
#endif

#ifndef mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST
#define mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST   (1U)
#endif

#if mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST == 0
#error "mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST must be greater than zero."
#endif

#if (mqttFileDownloader_CONFIG_BLOCK_SIZE * mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST) > (128U * 1024U)
#error "The requested MQTT stream response can exceed the AWS IoT MQTT streams 128 KB response limit."
#endif

#ifndef OTA_MAX_NUM_FILE_BLOCKS
#define OTA_MAX_NUM_FILE_BLOCKS                  (192U)
#endif

#endif /* MQTT_FILE_DOWNLOADER_CONFIG_H */
