package com.wheelchair.mypath.model;

import java.io.Serializable;

/**
 * @author Nadim Mahmud
 * @date 10/19/24
 */
public class Coordinate {
    double latitude;
    double longitude;
    double elevation;

    public Coordinate(double latitude, double longitude, double elevation) {
        this.latitude = latitude;
        this.longitude = longitude;
        this.elevation = elevation;
    }

    public double getLatitude() {
        return latitude;
    }

    public void setLatitude(double latitude) {
        this.latitude = latitude;
    }

    public double getLongitude() {
        return longitude;
    }

    public void setLongitude(double longitude) {
        this.longitude = longitude;
    }

    public double getElevation() {
        return elevation;
    }

    public void setElevation(double elevation) {
        this.elevation = elevation;
    }
}
