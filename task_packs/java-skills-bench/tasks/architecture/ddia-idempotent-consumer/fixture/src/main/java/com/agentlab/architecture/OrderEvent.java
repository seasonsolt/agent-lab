package com.agentlab.architecture;

public record OrderEvent(String eventId, String orderId, int version, String type, int amount) {
}
