package com.wheelchair.mypath.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;

/**
 * @author Nadim Mahmud
 * @date 2/21/25
 */
@RestController
public class BaseController {

    @GetMapping("/")
    public String getBaseUrl() throws IOException, InterruptedException {
        return "Hi there..";
    }
}
