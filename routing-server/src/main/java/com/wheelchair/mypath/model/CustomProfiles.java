package com.wheelchair.mypath.model;

/**
 * @author Nadim Mahmud
 * @date 2/24/25
 */
public enum CustomProfiles {
    WHEEL_CHAIR("wheelchair");

    private final String label;

    CustomProfiles(String label) {
        this.label = label;
    }

    public String getLabel(){
        return label;
    }
}
