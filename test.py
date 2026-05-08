import RPi.GPIO as GPIO
import time

# 1. Configuración de pines (BCM)
# ¡Atención! Cambia estos números por los pines GPIO reales que uses en tu Raspberry Pi.
# (Los 9, 8, 7, 6 de Arduino no se corresponden con los de la Raspberry)
filas_pin = [5, 6, 13, 19]     
columnas_pin = [12, 16, 20, 21] 

# 2. Definición del mapa de teclas (idéntico a tu Arduino)
teclas = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D']
]

def setup_teclado():
    GPIO.setmode(GPIO.BCM)
    
    # Configuramos los pines de las FILAS como SALIDAS (envían voltaje)
    for pin in filas_pin:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW) # Empezamos con 0V
        
    # Configuramos los pines de las COLUMNAS como ENTRADAS (leen voltaje)
    # Usamos PUD_DOWN para que internamente estén a 0V hasta que pulses una tecla
    for pin in columnas_pin:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def leer_teclado():
    """Escanea la matriz 4x4 y devuelve la tecla pulsada, o None si no hay nada."""
    tecla_pulsada = None
    
    for fila in range(len(filas_pin)):
        # Encendemos (3.3V) la fila actual
        GPIO.output(filas_pin[fila], GPIO.HIGH)
        
        for col in range(len(columnas_pin)):
            # Si leemos voltaje en esta columna, ¡bingo! Esa es la tecla.
            if GPIO.input(columnas_pin[col]) == GPIO.HIGH:
                tecla_pulsada = teclas[fila][col]
                # Pequeño retraso para evitar el "rebote" (que lea la tecla varias veces seguidas)
                time.sleep(0.3) 
                
        # Apagamos la fila actual antes de pasar a la siguiente
        GPIO.output(filas_pin[fila], GPIO.LOW)
        
    return tecla_pulsada

# 3. Bucle principal del programa
try:
    setup_teclado()
    print("Cámara acorazada iniciada. Introduce el PIN...")
    
    while True:
        tecla = leer_teclado()
        
        if tecla:
            print(f"Has pulsado: {tecla}")
            
        time.sleep(0.05) # Pequeña pausa para no saturar la CPU

except KeyboardInterrupt:
    # Se ejecuta si pulsas Ctrl+C para salir
    print("\nApagando sistema de seguridad...")
finally:
    # SIEMPRE hay que limpiar los pines al terminar para evitar cortocircuitos la próxima vez
    GPIO.cleanup()