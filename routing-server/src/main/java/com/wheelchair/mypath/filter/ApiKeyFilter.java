package com.wheelchair.mypath.filter;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;

import static java.util.Objects.isNull;

/**
 * @author Nadim Mahmud
 * @date 2/27/25
 */

@Component
public class ApiKeyFilter implements Filter {
    private static final Logger logger = LoggerFactory.getLogger(ApiKeyFilter.class);

    @Value("${api.key}")
    private String validApiKey;

    private static final String AUTHORIZATION_HEADER = "Authorization";
    private static final String BEARER_PREFIX = "Bearer ";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        String requestURI = httpRequest.getRequestURI();
        if (requestURI.startsWith("/route/") && !"OPTIONS".equalsIgnoreCase(httpRequest.getMethod())) {

            if (!isLocalRequest(httpRequest)) {
                String authorizationHeader = httpRequest.getHeader(AUTHORIZATION_HEADER);

                if (isNull(authorizationHeader) || !authorizationHeader.startsWith(BEARER_PREFIX)) {
                    logger.warn("Missing or invalid Authorization header for request to {}", requestURI);
                    httpResponse.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                    httpResponse.getWriter().write("Missing or invalid Authorization header");
                    return;
                }

                String apiKey = authorizationHeader.substring(BEARER_PREFIX.length());
                if (!validApiKey.equals(apiKey)) {
                    logger.warn("Invalid API key for request to {}", requestURI);
                    httpResponse.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                    httpResponse.getWriter().write("Invalid API Key");
                    return;
                }
            } else {
                logger.debug("Local request to {} — skipping API key check", requestURI);
            }
        }

        chain.doFilter(request, response);
    }

    /**
     * Returns true if the request originates from localhost/same server.
     * Checks the Origin header (browser requests) and the remote IP (direct requests).
     */
    private boolean isLocalRequest(HttpServletRequest request) {
        // For browser CORS requests, check the Origin header
        String origin = request.getHeader("Origin");
        if (origin != null) {
            return origin.contains("localhost") || origin.contains("127.0.0.1");
        }

        // For direct requests (curl, Postman from same machine), check the remote IP
        String remoteAddr = request.getRemoteAddr();
        return "127.0.0.1".equals(remoteAddr) || "::1".equals(remoteAddr) || "0:0:0:0:0:0:0:1".equals(remoteAddr);
    }
}
