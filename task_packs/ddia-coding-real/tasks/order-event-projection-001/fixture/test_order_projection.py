from order_projection import OrderProjector


def test_basic_happy_path():
    projector = OrderProjector()
    projector.apply({"event_id": "e1", "order_id": "o1", "version": 1, "type": "order_created", "amount": 42})
    projector.apply({"event_id": "e2", "order_id": "o1", "version": 2, "type": "payment_authorized"})
    projector.apply({"event_id": "e3", "order_id": "o1", "version": 3, "type": "order_shipped"})

    assert projector.orders["o1"]["status"] == "shipped"
    assert projector.orders["o1"]["amount"] == 42
