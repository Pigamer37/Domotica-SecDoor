import time, argparse, socket, json, re, threading

import paho.mqtt.client as mqtt

import Puertaseguridad

threadStop = threading.Event()


def printError(message):
    print(f"\x1b[31m{message}\x1b[39m")


def printInfo(message):
    print(f"\x1b[36m{message}\x1b[39m")


class DoorLogic:
    def __init__(self, broker_address, mqttPort, keep_alive_interval, host, port):
        self.password = "1234"

        printInfo(f"Creating TCP server at {host}:{port}")
        self.mySocket = socket.create_server(
            (host, port), family=socket.AF_INET, backlog=5
        )

        self.sockThread = threading.Thread(
            target=self.socket_listener, name="SocketListenerThread"
        )

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, transport="websockets"
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        printInfo(
            f"Connecting to MQTT broker at {broker_address}:{mqttPort} with keep-alive {keep_alive_interval} seconds."
        )
        self.client.connect(broker_address, mqttPort, keep_alive_interval)

    def socket_listener(self):
        while not threadStop.is_set():
            try:
                conn, addr = self.mySocket.accept()
                data = conn.recv(1024).decode().strip()
                printInfo(f"Received (TCP socket): '{data}'")
                if data != self.password:
                    self.alert("Unauthorized socket read attempt detected.")
                    conn.send("Unauthorized".encode())
                else:
                    conn.send(self.encode_json_sensor_data().encode())

                conn.close()
            except socket.error as e:
                if threadStop.is_set():
                    printInfo("Socket listener stopping due to stop signal.")
                else:
                    printError(f"Socket error: {e}")
                return  # Exit the listener on socket errors
            except Exception as e:
                printError(f"Socket accept interrupted: {e}")
                return  # Exit if the socket is closed

        printInfo("Closing TCP server socket...")
        self.mySocket.close()  # close the socket when stopping the listener

    def encode_json_sensor_data(self):
        # Simulate sensor data
        #sensor_data = {"temperature": 22.5, "humidity": 60, "door_status": "closed"}
        dist = Puertaseguridad.medir_distancia()
        if 0 < dist < 25:
            presence = True
        else:
            presence = False
        sensor_data = {"broker": self.client.host, "port": self.client.port, "presence": presence}
        return json.dumps(sensor_data)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            printError(
                f"Failed to connect: {reason_code}.\x1b[39m loop_forever() will retry connection"
            )
        else:
            printInfo(
                f"Connected flags: "
                + str(flags)
                + "; Result code: "
                + str(reason_code)
                + "; client1_id: "
                + str(client)
            )
            # Subscribing in on_connect() means that if we lose the connection and
            # reconnect then subscriptions will be renewed.
            self.client.subscribe("etsii/securityDoor/#")

    def on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        for i in range(len(reason_code_list)):
            if reason_code_list[i].is_failure:
                printError(
                    f"Broker rejected you subscription\x1b[39m: {reason_code_list[i]}"
                )

    def on_message(self, client, userdata, msg):
        decoded_payload = msg.payload.decode("utf-8")
        print("Received (" + msg.topic + "): " + str(decoded_payload))
        match msg.topic:
            case "etsii/securityDoor/unlock":
                if decoded_payload.strip() != self.password:
                    self.alert("Unauthorized unlock attempt detected.")
                else:
                    Puertaseguridad.abrir_puerta()
            case "etsii/securityDoor/resetPassword":
                self.reset_password(decoded_payload)
            case "etsii/securityDoor/alert":
                pass
            case _:
                printError("WARNING: Unknown topic. No action taken.")

    def reset_password(self, payload):
        try:
            previous, new = self._parse_password_payload(payload)
        except ValueError as exc:
            printError(f"Password reset failed: {exc}")
            return

        if previous != self.password:
            self.alert("Password reset failed: previous password does not match.")
            return

        self.password = new
        printInfo("Password successfully reset.")

    def _parse_password_payload(self, payload):
        cleaned = payload.strip()
        if any(x in cleaned for x in [",", ":", ";"]):
            parts = re.split(r"[,;:]", cleaned, maxsplit=1)
        else:
            raise ValueError(
                "payload must contain previous and new password separated by ';' ',' or ':'"
            )

        previous = parts[0].strip()
        new = parts[1].strip()
        if not previous or not new:
            raise ValueError("both previous and new password must be provided")

        return previous, new

    def alert(self, payload):
        self.client.publish("etsii/securityDoor/alert", payload)
        printInfo(f"Published to etsii/securityDoor/alert: {payload}")

    def start(self):
        printInfo("Starting MQTT client loop")
        self.client.loop_start()  # starts thread to process network traffic and dispatch callbacks
        printInfo("Starting TCP server thread")
        self.sockThread.start()

    def stop(self):
        print("--- Door Logic ---")
        printInfo("Stopping MQTT client")
        self.client.loop_stop()  # stops the network thread and disconnects from the broker
        printInfo("Stopping TCP server")
        threadStop.set()  # signal the thread to stop
        self.mySocket.shutdown(socket.SHUT_RDWR)  # unblock the accept() call
        self.mySocket.close()  # close the TCP socket
        self.sockThread.join()

    def disconnect(self):
        self.client.disconnect()  # disconnects from the broker


def main(args):
    print("--- Door Logic ---")
    printInfo("Press Ctrl+C to stop.")

    dl = DoorLogic(args.broker, args.mqtt_port, args.keep_alive, args.host, args.port)

    try:
        Puertaseguridad.setup()
        dl.start()
        cliente_detectado = False
        while True:
            dist = Puertaseguridad.medir_distancia()
            if 0 < dist < 25:  # Si hay alguien a menos de 50cm
                if not cliente_detectado:
                    print(f" ALERTA: Sujeto a {int(dist)}cm")
                    dl.alert(f"Subject detected at {int(dist)}cm")
                    cliente_detectado = True
            else:
                if cliente_detectado:
                    print(" Zona despejada.")
                    dl.alert(f"Subject left, zone clear")
                    cliente_detectado = False

            # 2. GESTIÓN DEL TECLADO
            tecla = Puertaseguridad.leer_teclado()
            if tecla:
                if tecla == "D":
                    Puertaseguridad.codigo_actual = Puertaseguridad.codigo_actual[:-1]
                    Puertaseguridad.actualizar_pantalla(
                        "PIN:", "*" * len(Puertaseguridad.codigo_actual)
                    )
                elif tecla == "#":
                    if Puertaseguridad.codigo_actual == dl.password:
                        # SECUENCIA JOYSTICK
                        paso = 0
                        t_inicio = time.time()
                        logrado = False
                        while (time.time() - t_inicio) < 15:
                            Puertaseguridad.actualizar_pantalla(
                                f"TIEMPO: {int(15-(time.time()-t_inicio))}s",
                                "SEQ: " + "*" * paso,
                            )
                            accion = Puertaseguridad.leer_joystick()
                            if accion != "CENTRO":
                                if accion == Puertaseguridad.SECUENCIA_SECRETA[paso]:
                                    paso += 1
                                    Puertaseguridad.beep(0.1)
                                    if paso == len(Puertaseguridad.SECUENCIA_SECRETA):
                                        logrado = True
                                        break
                                else:
                                    paso = 0
                                    Puertaseguridad.beep(0.5)
                                    time.sleep(0.5)
                                while Puertaseguridad.leer_joystick() != "CENTRO":
                                    time.sleep(0.1)
                            time.sleep(0.05)

                        if logrado:
                            Puertaseguridad.abrir_puerta()
                        else:
                            Puertaseguridad.actualizar_pantalla("ERROR", "BLOQUEADO")
                            dl.alert(
                                "Unauthorized access attempt detected via joystick."
                            )
                            time.sleep(2)
                        Puertaseguridad.codigo_actual = ""
                        Puertaseguridad.actualizar_pantalla(
                            "BANCO CENTRAL", "INTRODUZCA PIN"
                        )
                    else:
                        Puertaseguridad.actualizar_pantalla("PIN ERRONEO", "REINTENTE")
                        dl.alert("Unauthorized access attempt detected via keypad.")
                        Puertaseguridad.beep(0.6)
                        Puertaseguridad.codigo_actual = ""
                        time.sleep(2)
                        Puertaseguridad.actualizar_pantalla(
                            "BANCO CENTRAL", "INTRODUZCA PIN"
                        )
                elif len(Puertaseguridad.codigo_actual) < 4 and tecla not in [
                    "A",
                    "B",
                    "C",
                    "*",
                ]:
                    Puertaseguridad.codigo_actual += tecla
                    Puertaseguridad.actualizar_pantalla(
                        "PIN:", "*" * len(Puertaseguridad.codigo_actual)
                    )

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Stopping the door logic...")
        dl.stop()

    except Exception as e:
        printError(f"\nAn unexpected error occurred: {e}")
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
        "--mqtt-port",
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
    parser.add_argument(
        "--host",
        default="localhost",
        help="The host address for the TCP socket server.",
        required=False,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50007,
        help="The port for the TCP socket server.",
        required=False,
    )
    parser.add_argument("--verbose", action="store_true", help="Reduce output noise.")

    parsed_args = parser.parse_args()
    main(parsed_args)

