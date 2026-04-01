package com.wheelchair.mypath.model.apiresponse;

import com.wheelchair.mypath.model.Coordinate;

import java.util.ArrayList;
import java.util.List;

/**
 * @author Nadim Mahmud
 * @date 11/4/24
 */
public class Point {
    private Coordinate start_location;
    private Coordinate end_location;
    private List<Coordinate> points;
    private String surface;
    private Distance distance;
    private Duration duration;
    private String maneuver;
    private String travel_mode;
    private String instructions;
    private double incline;

    public Point(){
        points = new ArrayList<>();
    }

    public Coordinate getStart_location() {
        return start_location;
    }

    public void setStart_location(Coordinate start_location) {
        this.start_location = start_location;
    }

    public Coordinate getEnd_location() {
        return end_location;
    }

    public void setEnd_location(Coordinate end_location) {
        this.end_location = end_location;
    }

    public List<Coordinate> getPoints() {
        return points;
    }

    public void setPoints(List<Coordinate> points) {
        this.points = points;
    }

    public String getSurface() {
        return surface;
    }

    public void setSurface(String surface) {
        this.surface = surface;
    }

    public Distance getDistance() {
        return distance;
    }

    public void setDistance(Distance distance) {
        this.distance = distance;
    }

    public Duration getDuration() {
        return duration;
    }

    public void setDuration(Duration duration) {
        this.duration = duration;
    }

    public String getManeuver() {
        return maneuver;
    }

    public void setManeuver(String maneuver) {
        this.maneuver = maneuver;
    }

    public String getTravel_mode() {
        return travel_mode;
    }

    public void setTravel_mode(String travel_mode) {
        this.travel_mode = travel_mode;
    }

    public String getInstructions() {
        return instructions;
    }

    public double getIncline() {
        return incline;
    }

    public void setIncline(double incline) {
        this.incline = incline;
    }

    public void setInstructions(String instructions) {
        this.instructions = instructions;
    }

    public void addCoordinate(Coordinate coordinate) {
        getPoints().add(coordinate);
    }

    public Point cloneWithEmptyCoordinateList(){
        Point point = new Point();

        point.setStart_location(this.start_location);
        point.setEnd_location(this.end_location);
        point.setPoints(new ArrayList<>());
        point.setSurface(this.surface);
        point.setDistance(this.distance);
        point.setDuration(this.duration);
        point.setManeuver(this.maneuver);
        point.setTravel_mode(this.travel_mode);
        point.setInstructions(this.instructions);
        point.setIncline(this.incline);

        return point;
    }
}
