package com.agentlab.architecture;

import java.util.HashMap;
import java.util.Map;

public class OrderEventConsumer {
    private final Map<String, OrderView> orders = new HashMap<>();

    public void apply(OrderEvent event) {
        if ("order_created".equals(event.type())) {
            orders.put(event.orderId(), new OrderView("created", event.amount(), event.version()));
        } else if ("payment_authorized".equals(event.type())) {
            OrderView current = orders.get(event.orderId());
            orders.put(event.orderId(), new OrderView("paid", current.amount(), event.version()));
        } else if ("order_cancelled".equals(event.type())) {
            OrderView current = orders.get(event.orderId());
            orders.put(event.orderId(), new OrderView("cancelled", current.amount(), event.version()));
        }
    }

    public Map<String, OrderView> orders() {
        return orders;
    }
}
