package com.wheelchair.mypath.utils;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.graphhopper.jackson.Jackson;
import com.graphhopper.util.CustomModel;
import com.graphhopper.util.GHUtility;
import org.springframework.core.io.DefaultResourceLoader;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.stereotype.Component;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;

import static com.graphhopper.util.Helper.readJSONFileWithoutComments;
import static java.util.Objects.isNull;

/**
 * @author Nadim Mahmud
 * @date 2/24/25
 */
@Component
public class GHProfileUtils {

    private ResourceLoader resourceLoader;

    public GHProfileUtils() {
        resourceLoader = new DefaultResourceLoader();
    }

    public CustomModel loadCustomModel(String filePath) {
        try {
            Resource resource = resourceLoader.getResource("classpath:" + filePath);

            if (!resource.exists()) {
                throw new IllegalArgumentException("Resource not found: " + filePath);
            }

            InputStream is = resource.getInputStream();

            if (isNull(is)) {
                throw new IllegalArgumentException("There is no custom model '" + filePath + "'");
            }

            String json = readJSONFileWithoutComments(new InputStreamReader(is));
            ObjectMapper objectMapper = Jackson.newObjectMapper();

            return objectMapper.readValue(json, CustomModel.class);
        } catch (IOException e) {
            throw new IllegalArgumentException("Could not load custom model '" + filePath + "'");
        }
    }
}
