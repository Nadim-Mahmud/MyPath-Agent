package com.wheelchair.mypath.model.apiresponse;

import java.util.ArrayList;
import java.util.List;

/**
 * @author Nadim Mahmud
 * @date 11/4/24
 */
public class Route {
    private List<Point> points;

    public Route() {
        points = new ArrayList<>();
    }

    public List<Point> getPoints() {
        return points;
    }

    public void setPoints(List<Point> points) {
        this.points = points;
    }
}
