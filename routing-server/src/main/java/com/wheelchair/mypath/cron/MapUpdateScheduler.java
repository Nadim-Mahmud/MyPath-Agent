package com.wheelchair.mypath.cron;

import com.wheelchair.mypath.configurations.CustomGraphHopperConfig;
import com.wheelchair.mypath.service.MapService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import static com.wheelchair.mypath.constants.Constants.*;
import static com.wheelchair.mypath.utils.Utils.deleteDirectory;

/**
 * @author Nadim Mahmud
 * @date 2/27/25
 */
@Component
@EnableScheduling
public class MapUpdateScheduler {
    private static final Logger logger = LoggerFactory.getLogger(MapUpdateScheduler.class);

    @Autowired
    private CustomGraphHopperConfig graphHopperConfig;

    @Autowired
    private MapService cronService;

    @Scheduled(cron = "0 23 1 * * *") // Runs every day at 1:23 AM
    public void updateMapDaily() {
        try {
            logger.info("Scheduled weekly map update started");

            String newPbfPath = cronService.downloadMap();
            logger.info("Downloaded new .pbf file to {}", PBF_FILE);

            graphHopperConfig.updateMap(newPbfPath);

            deleteDirectory(PBF_FILE);
            deleteDirectory(PBF_PATH + "ohio.pbf");
            deleteDirectory(PBF_PATH + "maryland.pbf");
            deleteDirectory(PBF_PATH + "wisconsin.pbf");

            logger.info("Scheduled weekly map update completed successfully");
        } catch (Exception e) {
            logger.error("Failed to perform weekly map update: {}", e.getMessage(), e);
        }
    }
}