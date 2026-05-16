import RPi.GPIO as GPIO
import time
import smbus2
from RPLCD.i2c import CharLCD

# --- 1. CONFIGURACIÓN ---
DIRECCION_LCD = 0x27
DIRECCION_ADC = 0x4B
bus = smbus2.SMBus(1)

# Comandos ADS7830
COMANDO_CH0 = 0x84
COMANDO_CH1 = 0xC4

lcd = CharLCD("PCF8574", DIRECCION_LCD)

# Teclado 4x4
filas_pin = [5, 6, 13, 19]
columnas_pin = [12, 16, 20, 21]
teclas = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"],
]

# Otros Componentes
SERVO_PIN = 17
BUZZER_PIN = 22
LED_ROJO = 23
LED_VERDE = 24
JOYSTICK_SW = 25

# Sensor Ultrasónico
TRIG_PIN = 18
ECHO_PIN = 27

# Lógica de Seguridad
PIN_CORRECTO = "4927"
SECUENCIA_SECRETA = ["ARRIBA", "ARRIBA", "ABAJO", "IZQUIERDA", "PULSADO"]
codigo_actual = ""
cliente_detectado = False

# --- 2. FUNCIONES ---


def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Teclado
    for pin in filas_pin:
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
    for pin in columnas_pin:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # Joystick e Interfaz
    GPIO.setup(JOYSTICK_SW, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup([BUZZER_PIN, LED_ROJO, LED_VERDE], GPIO.OUT, initial=GPIO.LOW)

    # Ultrasónico
    GPIO.setup(TRIG_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(ECHO_PIN, GPIO.IN)

    # Servo
    GPIO.setup(SERVO_PIN, GPIO.OUT)
    global pwm
    pwm = GPIO.PWM(SERVO_PIN, 50)
    pwm.start(0)

    mover_servo(0)
    GPIO.output(LED_ROJO, GPIO.HIGH)
    actualizar_pantalla("SISTEMA ACTIVO", "INTRODUZCA PIN")
    print("--- Bóveda Iniciada (Monitorizando con Ultrasonido) ---")


def cambiar_contraseña(input_str):
    global PIN_CORRECTO
    PIN_CORRECTO = input_str.strip()


def medir_distancia():
    GPIO.output(TRIG_PIN, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, GPIO.LOW)

    inicio = time.time()
    fin = time.time()

    # Esperar a que el eco empiece y termine con un pequeño margen de seguridad
    timeout = time.time() + 0.04
    while GPIO.input(ECHO_PIN) == 0 and time.time() < timeout:
        inicio = time.time()
    while GPIO.input(ECHO_PIN) == 1 and time.time() < timeout:
        fin = time.time()

    distancia = ((fin - inicio) * 34300) / 2
    return distancia


def actualizar_pantalla(l1, l2=""):
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string(l1[:16])
    lcd.cursor_pos = (1, 0)
    lcd.write_string(l2[:16])


def beep(duracion=0.05):
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(duracion)
    GPIO.output(BUZZER_PIN, GPIO.LOW)


def mover_servo(angulo):
    duty = 2.5 + (10.0 * angulo / 180.0)
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)


def leer_teclado():
    for fila in range(len(filas_pin)):
        GPIO.output(filas_pin[fila], GPIO.HIGH)
        for col in range(len(columnas_pin)):
            if GPIO.input(columnas_pin[col]) == GPIO.HIGH:
                beep()
                time.sleep(0.3)
                GPIO.output(filas_pin[fila], GPIO.LOW)
                return teclas[fila][col]
        GPIO.output(filas_pin[fila], GPIO.LOW)
    return None


def leer_joystick():
    if GPIO.input(JOYSTICK_SW) == GPIO.LOW:
        return "PULSADO"
    try:
        x = bus.read_byte_data(DIRECCION_ADC, COMANDO_CH0)
        y = bus.read_byte_data(DIRECCION_ADC, COMANDO_CH1)
        m = 50
        if y < m:
            return "ARRIBA"
        elif y > (255 - m):
            return "ABAJO"
        elif x < m:
            return "IZQUIERDA"
        elif x > (255 - m):
            return "DERECHA"
        else:
            return "CENTRO"
    except:
        return "CENTRO"


def LED_verde():
    GPIO.output(LED_ROJO, GPIO.LOW)
    GPIO.output(LED_VERDE, GPIO.HIGH)


def LED_rojo():
    GPIO.output(LED_VERDE, GPIO.LOW)
    GPIO.output(LED_ROJO, GPIO.HIGH)


def abrir_puerta():
    actualizar_pantalla("ACCESO OK", "ABRIENDO...")
    LED_verde()
    mover_servo(90)
    for i in range(120, -1, -1):
        actualizar_pantalla("PUERTA ABIERTA", f"CIERRE: {i//60:02d}:{i%60:02d}")
        time.sleep(1)
    mover_servo(0)
    LED_rojo()


# --- 3. BUCLE PRINCIPAL ---
def main_bucle():
    global cliente_detectado, codigo_actual
    # 1. NOTIFICACIÓN POR TERMINAL (Ultrasonido)
    dist = medir_distancia()
    if 0 < dist < 50:  # Si hay alguien a menos de 50cm
        if not cliente_detectado:
            print(f"🚨 ALERTA: Sujeto a {int(dist)}cm")
            cliente_detectado = True
    else:
        if cliente_detectado:
            print("✅ Zona despejada.")
            cliente_detectado = False

    # 2. GESTIÓN DEL TECLADO
    tecla = leer_teclado()
    if tecla:
        if tecla == "D":
            codigo_actual = codigo_actual[:-1]
            actualizar_pantalla("PIN:", "*" * len(codigo_actual))
        elif tecla == "#":
            if codigo_actual == PIN_CORRECTO:
                # SECUENCIA JOYSTICK
                paso = 0
                t_inicio = time.time()
                logrado = False
                while (time.time() - t_inicio) < 15:
                    actualizar_pantalla(
                        f"TIEMPO: {int(15-(time.time()-t_inicio))}s",
                        "SEQ: " + "*" * paso,
                    )
                    accion = leer_joystick()
                    if accion != "CENTRO":
                        if accion == SECUENCIA_SECRETA[paso]:
                            paso += 1
                            beep(0.1)
                            if paso == len(SECUENCIA_SECRETA):
                                logrado = True
                                break
                        else:
                            paso = 0
                            beep(0.5)
                            time.sleep(0.5)
                        while leer_joystick() != "CENTRO":
                            time.sleep(0.1)
                    time.sleep(0.05)

                if logrado:
                    abrir_puerta()
                else:
                    actualizar_pantalla("ERROR", "BLOQUEADO")
                    time.sleep(2)
                codigo_actual = ""
                actualizar_pantalla("BANCO CENTRAL", "INTRODUZCA PIN")
            else:
                actualizar_pantalla("PIN ERRONEO", "REINTENTE")
                beep(0.6)
                codigo_actual = ""
                time.sleep(2)
                actualizar_pantalla("BANCO CENTRAL", "INTRODUZCA PIN")
        elif len(codigo_actual) < 4 and tecla not in ["A", "B", "C", "*"]:
            codigo_actual += tecla
            actualizar_pantalla("PIN:", "*" * len(codigo_actual))

    time.sleep(0.05)


if __name__ == "__main__":
    try:
        setup()
        while True:
            main_bucle()

    except KeyboardInterrupt:
        pwm.stop()
        GPIO.cleanup()
