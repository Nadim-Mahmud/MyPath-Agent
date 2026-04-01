package com.wheelchair.mypath.constants;

/**
 * @author Nadim Mahmud
 * @date 2/21/25
 */
public interface Constants {
    String PBF_URL = "https://download.geofabrik.de/north-america/us-latest.osm.pbf";

    String PBF_URL_OHIO = "https://download.geofabrik.de/north-america/us/ohio-latest.osm.pbf";
    String PBF_URL_MARYLAND = "https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf";
    String PBF_URL_WISCONSIN = "https://download.geofabrik.de/north-america/us/wisconsin-latest.osm.pbf";

    String PBF_PATH = "myPathDataStore/";
    String PBF_FILE = "myPathDataStore/map.pbf";
    String GH_CACHE_PATH = "myPathDataStore/routing-graph-cache";
    String GH_TMP_CACHE_PATH = "myPathDataStore/tmp-routing-graph-cache";
    String WHEELCHAIR_CUSTOM_MODEL_PATH = "custom-models/wheelchair.json";

    Double DEGREE_180 = 180.0;
    Double DEGREE_360 = 360.0;

    Double STRAIGHT_THRESHOLD = 13.0;
    Double SLIGHT_THRESHOLD = 45.0;
    Double STEEP_THRESHOLD = 90.0;

    Double AVG_SPEED = 5.0;
}
