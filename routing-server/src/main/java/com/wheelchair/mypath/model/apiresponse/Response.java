package com.wheelchair.mypath.model.apiresponse;

/**
 * @author Nadim Mahmud
 * @date 11/4/24
 */
public class Response {
    private Route routes;

    public Response() {
        this.routes = new Route();
    }

    public Route getRoutes() {
        return routes;
    }

    public void setRoutes(Route routes) {
        this.routes = routes;
    }
}
