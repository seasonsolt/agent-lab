import com.agentlab.architecture.OrderEvent;
import com.agentlab.architecture.OrderEventConsumer;
import com.agentlab.architecture.OrderView;

public class TestRunner {
    public static void main(String[] args) {
        assertLatePaymentIgnored(new OrderEvent("evt-late-91", "late-order-91", 4, "payment_authorized", 0));

        OrderEvent[] streamA = new OrderEvent[] {
            new OrderEvent("evt-A-create", "order-A-17", 10, "order_created", 123),
            new OrderEvent("evt-A-pay", "order-A-17", 11, "payment_authorized", 0),
            new OrderEvent("evt-A-pay", "order-A-17", 11, "payment_authorized", 0),
            new OrderEvent("evt-A-cancel", "order-A-17", 12, "order_cancelled", 0),
            new OrderEvent("evt-A-stale-pay", "order-A-17", 11, "payment_authorized", 0),
            new OrderEvent("evt-A-after-cancel", "order-A-17", 13, "payment_authorized", 0)
        };
        assertStreamResult(streamA, "order-A-17", new OrderView("cancelled", 123, 12), "stream A");

        OrderEvent[] streamB = new OrderEvent[] {
            new OrderEvent("evt-B-create", "order-B-29", 3, "order_created", 77),
            new OrderEvent("evt-B-pay", "order-B-29", 4, "payment_authorized", 0),
            new OrderEvent("evt-B-stale-create", "order-B-29", 2, "order_created", 999),
            new OrderEvent("evt-B-pay", "order-B-29", 4, "payment_authorized", 0),
            new OrderEvent("evt-B-cancel", "order-B-29", 6, "order_cancelled", 0),
            new OrderEvent("evt-B-after-cancel", "order-B-29", 7, "payment_authorized", 0)
        };
        assertStreamResult(streamB, "order-B-29", new OrderView("cancelled", 77, 6), "stream B");
    }

    private static void assertLatePaymentIgnored(OrderEvent event) {
        OrderEventConsumer consumer = new OrderEventConsumer();
        consumer.apply(event);
        assertTrue(!consumer.orders().containsKey(event.orderId()), "late payment must not create order");
    }

    private static void assertStreamResult(OrderEvent[] stream, String orderId, OrderView expected, String label) {
        OrderEventConsumer consumer = new OrderEventConsumer();
        for (OrderEvent event : stream) {
            consumer.apply(event);
        }
        assertEquals(expected, consumer.orders().get(orderId), label + " final state");

        for (OrderEvent event : stream) {
            consumer.apply(event);
        }
        assertEquals(expected, consumer.orders().get(orderId), label + " same-instance replay");

        OrderEventConsumer replay = new OrderEventConsumer();
        for (OrderEvent event : stream) {
            replay.apply(event);
        }
        for (OrderEvent event : stream) {
            replay.apply(event);
        }
        assertEquals(expected, replay.orders().get(orderId), label + " fresh replay");
    }

    private static void assertTrue(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError(label);
        }
    }

    private static void assertEquals(Object expected, Object actual, String label) {
        if (expected == null ? actual != null : !expected.equals(actual)) {
            throw new AssertionError(label + ": expected " + expected + " but got " + actual);
        }
    }
}
