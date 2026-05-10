import time, argparse

import paho.mqtt.client as mqtt


class DoorLogic:
    def __init__(self, broker_address, port, keep_alive_interval):
        self.password = "1234"

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, transport="websockets"
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        self.client.connect(broker_address, port, keep_alive_interval)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(
                f"Failed to connect: {reason_code}. loop_forever() will retry connection"
            )
        else:
            print(
                f"Connected flags: "
                + str(flags)
                + " result code: "
                + str(reason_code)
                + " client1_id: "
                + str(client)
            )
            # Subscribing in on_connect() means that if we lose the connection and
            # reconnect then subscriptions will be renewed.
            self.client.subscribe("etsii/securityDoor/#")

    def on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        for i in range(len(reason_code_list)):
            if reason_code_list[i].is_failure:
                print(f"Broker rejected you subscription: {reason_code_list[i]}")

    def on_message(self, client, userdata, msg):
        decoded_payload = msg.payload.decode("utf-8")
        print("Received (" + msg.topic + "): " + str(msg.payload))
        print("decoded message: ", decoded_payload)
        match msg.topic:
            case "etsii/securityDoor/unlock":
                if decoded_payload.strip() != self.password:
                    self.alert("Unauthorized unlock attempt detected.")
                else:
                    print("Unlocking the door...")
            case "etsii/securityDoor/resetPassword":
                self.reset_password(decoded_payload)
            case _:
                print("Unknown topic. No action taken.")

    def reset_password(self, payload):
        try:
            previous, new = self._parse_password_payload(payload)
        except ValueError as exc:
            print(f"Password reset failed: {exc}")
            return

        if previous != self.password:
            self.alert("Password reset failed: previous password does not match.")
            return

        self.password = new
        print("Password successfully reset.")

    def _parse_password_payload(self, payload):
        cleaned = payload.strip()
        if "," in cleaned:
            parts = cleaned.split(",", 1)
        elif ":" in cleaned:
            parts = cleaned.split(":", 1)
        else:
            raise ValueError(
                "payload must contain previous and new password separated by ',' or ':'"
            )

        previous = parts[0].strip()
        new = parts[1].strip()
        if not previous or not new:
            raise ValueError("both previous and new password must be provided")

        return previous, new

    def alert(self, payload):
        self.client.publish(
            "etsii/securityDoor/alert", payload
        )  # client.publish("/etsidi/val",23)
        print(f"Published to etsii/securityDoor/alert: {payload}")

    def start(self):
        self.client.loop_start()  # starts thread to process network traffic and dispatch callbacks

    def stop(self):
        self.client.loop_stop()  # stops the network thread and disconnects from the broker
        print("--- Door Logic ---")
        print("Disconnecting MQTT client")

    def disconnect(self):
        self.client.disconnect()  # disconnects from the broker


def main(args):
    print("--- Door Logic ---")
    print(
        f"Connecting to MQTT broker at {args.broker}:{args.port} with keep-alive {args.keep_alive} seconds."
    )
    print("Press Ctrl+C to stop.")

    dl = DoorLogic(args.broker, args.port, args.keep_alive)

    try:
        dl.start()
        while True:
            time.sleep(1.5)
            print("Hola")
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Stopping the door logic...")
        dl.stop()

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        dl.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Launches a mqtt client and TCP socket server for a security door."
    )
    parser.add_argument(
        "--broker",
        default="broker.hivemq.com",
        help="The IP address of the MQTT broker.",
        required=False,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="The port of the MQTT broker.",
        required=False,
    )
    parser.add_argument(
        "--keep-alive",
        type=int,
        default=60,
        help="Keep alive interval in seconds (default: 60).",
    )
    parser.add_argument("--verbose", action="store_true", help="Reduce output noise.")

    parsed_args = parser.parse_args()
    main(parsed_args)
