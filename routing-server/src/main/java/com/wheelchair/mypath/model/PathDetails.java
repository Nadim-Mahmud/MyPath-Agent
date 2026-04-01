package com.wheelchair.mypath.model;

/**
 * @author Nadim Mahmud
 * @date 2/24/25
 */
public enum PathDetails {
    SURFACE("surface"),
    STREET_NAME("street_name"),
    FOOT_WAY("footway");

    private final String label;

    PathDetails(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}
