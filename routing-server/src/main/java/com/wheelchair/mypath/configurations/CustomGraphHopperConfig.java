package com.wheelchair.mypath.configurations;

import com.graphhopper.GraphHopperConfig;
import com.graphhopper.config.CHProfile;
import com.graphhopper.config.Profile;
import com.graphhopper.GraphHopper;
import com.graphhopper.reader.dem.SRTMProvider;
import com.wheelchair.mypath.service.MapService;
import com.wheelchair.mypath.utils.GHProfileUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.support.DefaultListableBeanFactory;
import org.springframework.context.ApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.nio.file.Files;
import java.nio.file.Path;

import java.io.IOException;

import static com.wheelchair.mypath.constants.Constants.*;
import static com.wheelchair.mypath.model.CustomProfiles.WHEEL_CHAIR;
import static com.wheelchair.mypath.utils.Utils.deleteDirectory;
import static com.wheelchair.mypath.utils.Utils.downloadFile;
import static java.nio.file.Files.exists;
import static java.nio.file.Path.of;
import static java.util.Objects.nonNull;

/**
 * @author Nadim Mahmud
 * @date 2/21/25
 */
@Configuration
public class CustomGraphHopperConfig {
    private static final Logger logger = LoggerFactory.getLogger(CustomGraphHopperConfig.class);
    private volatile GraphHopper hopper;
    @Autowired
    private GHProfileUtils ghProfileUtils;

    @Autowired
    private ApplicationContext applicationContext;

    @Autowired
    private MapService mapService;

    @Bean
    public GraphHopper graphHopper() throws IOException, InterruptedException {
        hopper = createGraphHopperFromPbf(PBF_FILE, GH_CACHE_PATH);
        hopper.importOrLoad();
        logger.info("Initial GraphHopper instance loaded with cache at {}", GH_CACHE_PATH);

        return hopper;
    }

    public synchronized void updateMap(String newPbfPath) throws IOException, InterruptedException {
        logger.info("Starting map update with .pbf file: {}", newPbfPath);

        GraphHopper newHopper = createGraphHopperFromPbf(newPbfPath, GH_TMP_CACHE_PATH);
        newHopper.importOrLoad();
        logger.info("New GraphHopper instance initialized with cache at {}", GH_TMP_CACHE_PATH);

        GraphHopper oldHopper = hopper;
        hopper = newHopper;
        logger.info("Swapped to new GraphHopper instance");

        refreshGraphHopperBean(newHopper);

        if (nonNull(oldHopper)) {
            oldHopper.close();
            logger.info("Closed old GraphHopper instance");
        }

        Path oldCacheDir = of(GH_CACHE_PATH);

        if (exists(oldCacheDir)) {
            deleteDirectory(GH_CACHE_PATH);
            logger.info("Deleted old cache directory at {}", GH_CACHE_PATH);
        }

        Files.move(of(GH_TMP_CACHE_PATH), oldCacheDir);
        logger.info("Moved new cache from {} to {}", GH_TMP_CACHE_PATH, GH_CACHE_PATH);
    }

    private GraphHopper createGraphHopperFromPbf(String pbfPath, String cachePath) throws IOException, InterruptedException {

        if (!exists(of(pbfPath))) {
            logger.info("Downloading the pbf to {} as it do not exists by default", PBF_FILE);
            mapService.downloadMap();

            return createGraphHopperFromPbf(PBF_FILE, cachePath);
        }

        GraphHopperConfig graphHopperConfig = new GraphHopperConfig();
        graphHopperConfig.putObject("graph.dataaccess.default_type", "MMAP");

        GraphHopper hopper = new GraphHopper();

        hopper.setOSMFile(pbfPath);
        hopper.setGraphHopperLocation(cachePath);
        hopper.setEncodedValuesString("foot_access, hike_rating, mtb_rating, foot_priority, foot_average_speed, average_slope, max_slope, surface, footway, smoothness, country, road_class");
        hopper.setElevationProvider(new SRTMProvider());

        Profile wheelChair = new Profile(WHEEL_CHAIR.getLabel()).setCustomModel(ghProfileUtils.loadCustomModel(WHEELCHAIR_CUSTOM_MODEL_PATH));
        hopper.setProfiles(wheelChair);
        hopper.getCHPreparationHandler().setCHProfiles(new CHProfile(WHEEL_CHAIR.getLabel()));

        return hopper;
    }

    private void refreshGraphHopperBean(GraphHopper newHopper) {
        ConfigurableApplicationContext configurableContext = (ConfigurableApplicationContext) applicationContext;
        DefaultListableBeanFactory beanFactory = (DefaultListableBeanFactory) configurableContext.getBeanFactory();

        if (beanFactory.containsSingleton("graphHopper")) {
            beanFactory.destroySingleton("graphHopper");
        }

        beanFactory.registerSingleton("graphHopper", newHopper);
        logger.info("GraphHopper bean refreshed in the application context");
    }

    public GraphHopper getHopper() {
        return hopper;
    }
}