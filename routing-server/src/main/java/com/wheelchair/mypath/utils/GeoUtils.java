package com.wheelchair.mypath.utils;

import com.wheelchair.mypath.model.Coordinate;
import com.wheelchair.mypath.model.TurnDirection;

import static com.wheelchair.mypath.constants.Constants.*;
import static com.wheelchair.mypath.model.TurnDirection.*;

/**
 * @author Nadim Mahmud
 * @date 10/19/24
 */
public class GeoUtils {

    public static double distance(double lat1, double lon1, double lat2, double lon2) {
        // * https://www.movable-type.co.uk/scripts/latlong.html

        double dLat = Math.toRadians(lat1 - lat2);
        double dLon = Math.toRadians(lon1 - lon2);

        double radianLat1 = Math.toRadians(lat2);
        double radianLat2 = Math.toRadians(lat1);

        double haversineFormula = Math.pow(Math.sin(dLat / 2), 2)
                + Math.pow(Math.sin(dLon / 2), 2)
                * Math.cos(radianLat1) * Math.cos(radianLat2);

        double rad = 6371;
        double c = 2 * Math.asin(Math.sqrt(haversineFormula));
        return rad * c;
    }

    public static double calcDistance(Coordinate coordinate1, Coordinate coordinate2) {
        return distance(coordinate1.getLatitude(),
                coordinate1.getLongitude(),
                coordinate2.getLatitude(),
                coordinate2.getLongitude());
    }

    //bearing=atan2(sin(Δlon)⋅cos(lat2),cos(lat1)⋅sin(lat2)−sin(lat1)⋅cos(lat2)⋅cos(Δlon))
    //Δlon=lon2−lon1
    public static double calculateBearing(Coordinate point1, Coordinate point2) {
        // Convert latitude and longitude from degrees to radians
        double lat1Rad = Math.toRadians(point1.getLatitude());
        double lon1Rad = Math.toRadians(point1.getLongitude());
        double lat2Rad = Math.toRadians(point2.getLatitude());
        double lon2Rad = Math.toRadians(point2.getLongitude());

        double dLon = lon2Rad - lon1Rad;

        // Calculate the bearing
        double y = Math.sin(dLon) * Math.cos(lat2Rad);
        double x = Math.cos(lat1Rad) * Math.sin(lat2Rad) -
                Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon);
        double initialBearing = Math.atan2(y, x);

        // Convert the result from radians to degrees and normalize it to [0, 360)
        initialBearing = Math.toDegrees(initialBearing);

        return (initialBearing + 360) % 360;
    }

    // Method to calculate the heading change between three coordinates
    /*
        headingchange=(bearingBC−bearingAB+360)mod360
     */
    public static double calculateHeading(Coordinate pointA, Coordinate pointB, Coordinate pointC) {
        double bearingAB = calculateBearing(pointA, pointB);
        double bearingBC = calculateBearing(pointB, pointC);

        // Calculate the heading change
        double headingChange = (bearingBC - bearingAB + 360) % 360;

        return headingChange;
    }

    public static TurnDirection getTurnDirection(Coordinate start, Coordinate mid, Coordinate end) {

        double headingChange = calculateHeading(start, mid, end);

        if (headingChange > DEGREE_180) {
            headingChange -= DEGREE_360;
        } else if (headingChange < -DEGREE_180) {
            headingChange += DEGREE_360;
        }

        double absChange = Math.abs(headingChange);

        if (absChange <= STRAIGHT_THRESHOLD) {
            return STRAIGHT;
        } else if (headingChange > 0) {

            if (absChange <= SLIGHT_THRESHOLD) {
                return SLIGHT_RIGHT;
            } else if (absChange <= STEEP_THRESHOLD) {
                return RIGHT;
            } else {
                return STEEP_RIGHT;
            }
        } else {

            if (absChange <= SLIGHT_THRESHOLD) {
                return SLIGHT_LEFT;
            } else if (absChange <= STEEP_THRESHOLD) {
                return LEFT;
            } else {
                return STEEP_LEFT;
            }
        }
    }

    public static double calculateInclinePercent(Coordinate src, Coordinate dest) {
        double distance = calcDistance(src, dest) * 1000; // to meter
        double elevationChange = src.getElevation() - dest.getElevation();

        return (elevationChange / distance) * 100.0;
    }
}
