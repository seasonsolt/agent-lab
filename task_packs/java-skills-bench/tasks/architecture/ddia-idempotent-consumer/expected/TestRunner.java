import com.agentlab.architecture.OrderEvent;
import com.agentlab.architecture.OrderEventConsumer;
import com.agentlab.architecture.OrderView;

public class TestRunner {
    public static void main(String[] args) {
        OrderEventConsumer consumer = new OrderEventConsumer();

        consumer.apply(new OrderEvent("late-pay", "o2", 2, "payment_authorized", 0));
        assertTrue(!consumer.orders().containsKey("o2"), "late payment must not create order");

        consumer.apply(new OrderEvent("e1", "o1", 1, "order_created", 42));
        consumer.apply(new OrderEvent("e2", "o1", 2, "payment_authorized", 0));
        consumer.apply(new OrderEvent("e2", "o1", 2, "payment_authorized", 0));
        consumer.apply(new OrderEvent("e4", "o1", 4, "order_cancelled", 0));
        consumer.apply(new OrderEvent("e3", "o1", 3, "payment_authorized", 0));
        consumer.apply(new OrderEvent("e5", "o1", 5, "payment_authorized", 0));

        OrderView order = consumer.orders().get("o1");
        assertEquals("cancelled", order.status(), "cancellation remains terminal");
        assertEquals(42, order.amount(), "amount preserved");
        assertEquals(5, order.version(), "version evidence advances for invalid newer event");

        OrderEventConsumer replay = new OrderEventConsumer();
        OrderEvent[] stream = new OrderEvent[] {
            new OrderEvent("e1", "o1", 1, "order_created", 42),
            new OrderEvent("e2", "o1", 2, "payment_authorized", 0),
            new OrderEvent("e2", "o1", 2, "payment_authorized", 0),
            new OrderEvent("e4", "o1", 4, "order_cancelled", 0),
            new OrderEvent("e3", "o1", 3, "payment_authorized", 0),
            new OrderEvent("e5", "o1", 5, "payment_authorized", 0)
        };
        for (OrderEvent event : stream) {
            replay.apply(event);
        }
        for (OrderEvent event : stream) {
            replay.apply(event);
        }
        assertEquals(order, replay.orders().get("o1"), "replay is idempotent");
    }

    private static void assertTrue(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError(label);
        }
    }

    private static void assertEquals(Object expected, Object actual, String label) {
        if (!expected.equals(actual)) {
            throw new AssertionError(label + ": expected " + expected + " but got " + actual);
        }
    }
}
