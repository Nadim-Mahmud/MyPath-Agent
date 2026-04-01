package com.wheelchair.mypath.exceptions;

import org.springframework.http.HttpStatus;

/**
 * @author Nadim Mahmud
 * @date 2/24/25
 */
public class RouteNotFound extends RuntimeException {

    private final HttpStatus status;

    public RouteNotFound(String message) {
        super(message);

        this.status = HttpStatus.NOT_FOUND;
    }

    public HttpStatus getStatus() {
        return status;
    }
}