package com.wheelchair.mypath.utils;

import static java.util.Objects.nonNull;

/**
 * @author Nadim Mahmud
 * @date 11/3/24
 */
public class StringUtils {

    public static String emptyString(){
        return "";
    }

    public static String getString(Object str) {
        return nonNull(str) ? str.toString() : null;
    }
}
