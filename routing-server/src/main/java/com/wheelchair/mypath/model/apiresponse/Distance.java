package com.wheelchair.mypath.model.apiresponse;

/**
 * @author Nadim Mahmud
 * @date 11/4/24
 */
public class Distance {
    private String text;
    private String type;
    private double value;

    public String getText() {
        return text;
    }

    public void setText(String text) {
        this.text = text;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public double getValue() {
        return value;
    }

    public void setValue(double value) {
        this.value = value;
    }
}
