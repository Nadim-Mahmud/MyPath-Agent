package com.wheelchair.mypath.service;

import com.wheelchair.mypath.utils.Utils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;

import static com.wheelchair.mypath.constants.Constants.*;
import static com.wheelchair.mypath.utils.Utils.downloadFile;

/**
 * @author Nadim Mahmud
 * @date 4/28/25
 */
@Service
public class MapService {
    private static final Logger logger = LoggerFactory.getLogger(MapService.class);


    public String downloadMap() throws IOException, InterruptedException {
        logger.info("Map download started");

//        String ohioMapPath = downloadFile(PBF_URL_OHIO, PBF_PATH + "ohio.pbf");
//        String marylandMapPath = downloadFile(PBF_URL_MARYLAND, PBF_PATH + "maryland.pbf");
//        String wisconsinMapPath = downloadFile(PBF_URL_WISCONSIN, PBF_PATH + "wisconsin.pbf");
//
//        logger.info("Map merge operation started");
//
//        String mergedMapPath = Utils.mergePbfMap(
//                PBF_PATH + "ohio.pbf",
//                PBF_PATH + "maryland.pbf",
//                PBF_PATH + "wisconsin.pbf"
//        );

//        logger.info("Map download and preprocessing completed");
//
//        return mergedMapPath;

        String ohioMapPath = downloadFile(PBF_URL_OHIO, PBF_FILE);

        return ohioMapPath;
    }
}
