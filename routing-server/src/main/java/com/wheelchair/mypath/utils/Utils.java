package com.wheelchair.mypath.utils;

import com.graphhopper.reader.osm.pbf.PbfReader;
import com.wheelchair.mypath.cron.MapUpdateScheduler;
import org.openstreetmap.osmosis.core.Osmosis;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static com.wheelchair.mypath.constants.Constants.PBF_FILE;
import static com.wheelchair.mypath.constants.Constants.PBF_PATH;
import static java.nio.file.Path.of;
import static java.nio.file.StandardCopyOption.REPLACE_EXISTING;

/**
 * @author Nadim Mahmud
 * @date 2/24/25
 */
public class Utils {

    private static final Logger logger = LoggerFactory.getLogger(Utils.class);

    //get inclusive sub array [start, end]
    public static <T> List<T> getSubArray(List<T> arrayList, int start, int end) {

        return new ArrayList<>(arrayList.subList(start, end+1));
    }

    public static void deleteDirectory(String filePath) throws IOException {
        Path directory =  of(filePath);

        Files.walk(directory)
                .sorted((a, b) -> b.compareTo(a))
                .forEach(path -> {
                    try {
                        Files.delete(path);
                    } catch (IOException e) {
                        throw new RuntimeException("Failed to delete " + path, e);
                    }
                });
    }

    public static String downloadFile(String url, String downloadPath) throws IOException {
        logger.info("Downloading from url: {}", url);
        Files.copy(new URL(url).openStream(), of(downloadPath), REPLACE_EXISTING);

        return downloadPath;
    }

    public static String mergePbfMap(String... inputFiles) throws InterruptedException, IOException {
        if (inputFiles == null || inputFiles.length < 2) {
            throw new IllegalArgumentException("At least two input files are required for merging.");
        }

        String mergedFilePath = PBF_FILE;

        List<String> command = new ArrayList<>();
        command.add("osmosis");

        for (String input : inputFiles) {
            command.add("--read-pbf");
            command.add("file=" + input);
        }

        for (int i = 1; i < inputFiles.length; i++) {
            command.add("--merge");
        }

        command.add("--write-pbf");
        command.add("file=" + mergedFilePath);

        ProcessBuilder pb = new ProcessBuilder(command);
        pb.directory(new File(System.getProperty("user.dir")));
        pb.inheritIO();

        Process process = pb.start();
        int exitCode = process.waitFor();

        if (exitCode != 0) {
            throw new RuntimeException("Osmosis failed with exit code " + exitCode);
        }

        return mergedFilePath;
    }

}
