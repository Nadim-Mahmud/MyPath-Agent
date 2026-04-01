package com.wheelchair.mypath.utils;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.TimeZone;

/**
 * @author Nadim Mahmud
 * @date 11/3/24
 */
public class DateUtils {

    public static Date getDate(String timestamp) {
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssX");
        sdf.setTimeZone(TimeZone.getTimeZone("UTC"));

        try {
            return sdf.parse(timestamp);
        } catch (ParseException e) {
            e.printStackTrace();
        }

        return null;
    }
}
