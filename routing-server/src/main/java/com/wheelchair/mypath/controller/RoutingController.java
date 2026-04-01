package com.wheelchair.mypath.controller;

import com.graphhopper.GHResponse;
import com.graphhopper.ResponsePath;
import com.wheelchair.mypath.model.apiresponse.Response;
import com.wheelchair.mypath.service.RoutingService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * @author Nadim Mahmud
 * @date 2/21/25
 */
@RestController
@RequestMapping("/route/*")
public class RoutingController {

    @Autowired
    private RoutingService routingService;

    @GetMapping(value = "/getSingleRoute")
    public Response getRoute(
            @RequestParam double srcLat,
            @RequestParam double srcLon,
            @RequestParam double destLat,
            @RequestParam double destLon) {

        return routingService.getBestRoute(srcLat, srcLon, destLat, destLon);
    }
}