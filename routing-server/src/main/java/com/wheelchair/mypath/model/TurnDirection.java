package com.wheelchair.mypath.model;

/**
 * @author Nadim Mahmud
 * @date 2/24/25
 */
public enum TurnDirection {
    LEFT("Turn left"),
    SLIGHT_LEFT("Turn slightly left"),
    STEEP_LEFT("Make a steep left turn"),
    RIGHT("Turn right"),
    SLIGHT_RIGHT("Turn slightly right"),
    STEEP_RIGHT("Make a steep right turn"),
    STRAIGHT("Go straight"),
    END("Reached");

    private final String label;

    TurnDirection(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}
