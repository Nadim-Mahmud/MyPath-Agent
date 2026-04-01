package com.wheelchair.mypath.service;

import com.graphhopper.ResponsePath;
import com.graphhopper.util.PointList;
import com.graphhopper.util.details.PathDetail;
import com.graphhopper.util.shapes.GHPoint3D;
import com.wheelchair.mypath.exceptions.RouteNotFound;
import com.wheelchair.mypath.model.Coordinate;
import com.wheelchair.mypath.model.TurnDirection;
import com.wheelchair.mypath.model.apiresponse.*;
import com.wheelchair.mypath.utils.GeoUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import static com.wheelchair.mypath.constants.Constants.*;
import static com.wheelchair.mypath.model.PathDetails.SURFACE;
import static com.wheelchair.mypath.model.TurnDirection.END;
import static com.wheelchair.mypath.model.TurnDirection.STRAIGHT;
import static com.wheelchair.mypath.utils.GeoUtils.*;
import static com.wheelchair.mypath.utils.Utils.getSubArray;

/**
 * @author Nadim Mahmud
 * @date 2/24/25
 */
@Service
public class NavigationService {
    private static final Logger logger = LoggerFactory.getLogger(NavigationService.class);

    public static final int SECOND_INDEX = 1;

    public Response getNavigation(ResponsePath responsePath) {
        return generateResponse(responsePath);
    }

    private Response generateResponse(ResponsePath responsePath) {
        logger.info("Generating structured route!");

        List<Coordinate> coordinateList = getRouteCoordinates(responsePath);

        if(coordinateList.size() <=2) {
            throw new RouteNotFound("Route not found!");
        }

        Map<String, List<PathDetail>> pathDetails = responsePath.getPathDetails();

        List<Point> pointList = getPointListGroupedBySurface(coordinateList, pathDetails);

        pointList = processManeuverSegments(pointList);
        pointList = processSegmentsStartEnd(pointList);
        pointList = generateManeuverInfos(pointList);

        pointList = calcIncline(pointList);
        processDistance(pointList);
        processDuration(pointList);

        Route route = new Route();
        route.setPoints(pointList);

        Response response = new Response();
        response.setRoutes(route);

        return response;
    }

    private List<Point> getPointListGroupedBySurface(List<Coordinate> coordinateList, Map<String, List<PathDetail>> pathDetails) {
        List<PathDetail> surfaceList = pathDetails.get(SURFACE.getLabel());
        List<Point> pointList = new ArrayList<>();

        for (PathDetail pathDetail: surfaceList) {
            Point point = new Point();

            point.setSurface((String) pathDetail.getValue());
            point.setPoints(getSubArray(coordinateList, pathDetail.getFirst(), pathDetail.getLast()));

            pointList.add(point);
        }

        return pointList;
    }

    private List<Point> processManeuverSegments(List<Point> pointList) {
        List<Point> points = new ArrayList<>();

        for (Point point : pointList) {
            if (point.getPoints().size() <= 2) {
                points.add(point);
            } else {
                List<Coordinate> coordinateList = point.getPoints();
                Point newPoint = createNewSegment(point, coordinateList.get(0), coordinateList.get(1));
                points.add(newPoint);

                for (int i = 2; i < coordinateList.size(); i++) {
                    Coordinate start = coordinateList.get(i - 2);
                    Coordinate mid = coordinateList.get(i - 1);
                    Coordinate end = coordinateList.get(i);

                    TurnDirection turnDirection = getTurnDirection(start, mid, end);

                    if (turnDirection == STRAIGHT ) {
                        newPoint.addCoordinate(end);
                    } else {
                        newPoint = createNewSegment(point, mid, end);
                        points.add(newPoint);
                    }
                }
            }
        }

        return points;
    }

    private List<Point> processSegmentsStartEnd(List<Point> points) {
        for (Point point : points) {
            List<Coordinate> coordinateList = point.getPoints();
            point.setStart_location(coordinateList.get(0));
            point.setEnd_location(coordinateList.get(coordinateList.size() - 1));
        }

        return points;
    }

    private List<Point> generateManeuverInfos(List<Point> pointList) {
        for (int i = 0; i < pointList.size() - 1; i++) {
            Point currentSegment = pointList.get(i);
            Point nextSegment = pointList.get(i+1);

            Coordinate start = currentSegment.getPoints().get(currentSegment.getPoints().size() - 2);
            Coordinate mid = currentSegment.getEnd_location();
            Coordinate end = nextSegment.getPoints().get(SECOND_INDEX);

            System.out.println();
            currentSegment.setManeuver(getTurnDirection(start, mid, end).getLabel());
        }

        pointList.get(pointList.size()-1).setManeuver(END.getLabel());

        return pointList;
    }

    private void processDistance(List<Point> pointList) {
        Double distance = 0.0;

        for (Point point : pointList) {
            distance = 0.0;
            List<Coordinate> coordinateList = point.getPoints();

            for (int i = 1; i < coordinateList.size(); i++) {
                distance += calcDistance(coordinateList.get(i - 1), coordinateList.get(i));
            }

            double distanceInFeet = distance * 3280.84;
            double distanceInMi = distance * 0.621371;

            Distance segmentDistance = new Distance();
            segmentDistance.setValue(distanceInFeet);
            segmentDistance.setType("feet");
            segmentDistance.setText(String.format("%.2f", distanceInMi) + " mi");

            point.setDistance(segmentDistance);
        }
    }

    private void processDuration(List<Point> points) {
        for (Point point : points) {
            double timeInSecond = (point.getDistance().getValue() * 3600.0) / (5280 * AVG_SPEED);
            double timeInMinute = timeInSecond / 60;

            Duration duration = new Duration();
            duration.setValue(timeInSecond);
            duration.setType("second");
            duration.setText(String.format("%.2f", timeInMinute) + " min");

            point.setDuration(duration);
        }
    }

    private List<Point> calcIncline(List<Point> pointList) {
        for( Point point: pointList) {
            point.setIncline(calculateInclinePercent(point.getStart_location(), point.getEnd_location()));
        }

        return pointList;
    }

    private Point createNewSegment(Point point, Coordinate coo1, Coordinate coo2) {
        Point newPoint = point.cloneWithEmptyCoordinateList();
        newPoint.addCoordinate(coo1);
        newPoint.addCoordinate(coo2);

        return newPoint;
    }

    private List<Coordinate> getRouteCoordinates(ResponsePath responsePath) {
        PointList pointList = responsePath.getPoints();
        List<Coordinate> coordinateList = new ArrayList<>();

        for (int i = 0; i < pointList.size(); i++) {
            GHPoint3D ghPoint3D = pointList.get(i);
            coordinateList.add(new Coordinate(ghPoint3D.getLat(), ghPoint3D.getLon(), ghPoint3D.getEle()));
        }

        return coordinateList;
    }
}
