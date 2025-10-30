from flask import Flask, request, jsonify, g  # Agregado g para la conexión DB global.
import mysql.connector 
from datetime import datetime, timedelta  # Agregado timedelta para calcular diferencias de tiempo.
from mysql.connector import Error
from dotenv import load_dotenv 
import os

# Carga variables de entorno (asegúrate de tener un .env con DB_HOST, etc.)
load_dotenv()

app = Flask(__name__)  # Crea la app Flask.

# Configuración de la conexión a MySQL (cambia con tus datos).
db_config = {
    "host": os.getenv("DB_HOST"), 
    "port": os.getenv("DB_PORT"),    
    "user": os.getenv("DB_USER"),  
    "password": os.getenv("DB_PASSWORD"),  
    "database": os.getenv("DB_NAME")
}

print(db_config)  # Para depurar configuración.

# Función para la conexión a la base de datos MySQL (antes de cada request).
@app.before_request 
def conexion_db():
    """Establece la conexión a la base de datos antes de cada solicitud."""
    try:
        g.db = mysql.connector.connect(**db_config) 
        g.db_cursor = g.db.cursor(dictionary=True)  # Cursor con diccionarios para facilitar acceso.
    except mysql.connector.Error as err: 
        g.db = None 
        g.db_cursor = None
        print(f"Error de conexión: {err}")

# Función para cerrar la conexión después de cada request.
@app.teardown_request
def teardown_request(exception):
    """Cierra la conexión después de cada solicitud."""
    if hasattr(g, 'db') and g.db is not None:
        g.db.close() 
    if hasattr(g, 'db_cursor') and g.db_cursor is not None: 
        g.db_cursor.close()

@app.route('/')
def mostrar_empleados():
    if g.db_cursor is None:
        return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
    try:
        g.db_cursor.execute("""
            SELECT e.id_empleado, e.nombre, e.apellido, e.email, e.puesto_trabajo, e.telefono, 
                   t.nombre AS tienda_nombre, u.genero, e.activo
            FROM empleados e
            JOIN tiendas t ON e.id_tienda = t.id_tienda
            JOIN usuarios u ON e.id_empleado = u.id_empleado
        """)
        empleados = g.db_cursor.fetchall()
        print(f"Empleados encontrados: {len(empleados)}")  # Log para depurar | Parece haber solo 1 empleado por alguna razón (el empleado no esta en usuarios)
        return jsonify(empleados)
    except Exception as e:
        return jsonify({"error": f"Error al listar empleados: {e}"}), 500

# Ruta para registro de asistencia RFID
@app.route('/registro', methods=['POST'])
def registrar_asistencia():
    if g.db_cursor is None:
        return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
    
    try:
        # Obtiene datos del JSON enviado por el dispositivo RFID.
        data = request.get_json()
        id_empleado = data.get('id_empleado') 
        tipo = data.get('tipo', 'entrada').lower()  # Convertir a minuscula, ej:'entrada'.
        
        if not id_empleado:
            return jsonify({"error": "Falta id_empleado"}), 400
        
        # Valida que tipo sea solo 'entrada' o 'salida'.
        if tipo not in ['entrada', 'salida']:
            return jsonify({"error": "Tipo inválido. Solo 'entrada' o 'salida'"}), 400
        
        # Obtiene fecha y hora actuales.
        fecha = datetime.now().date()
        hora_actual = datetime.now()
        
        # Chequea si ya existe un registro con la misma fecha, id_empleado y tipo.
        g.db_cursor.execute("""
            SELECT COUNT(*) as count FROM asistencia 
            WHERE id_empleado = %s AND fecha = %s AND tipo = %s
        """, (id_empleado, fecha, tipo))
        existing_same_type = g.db_cursor.fetchone()['count']
        if existing_same_type > 0:
            return jsonify({"error": "El empleado ya marco su asistencia del dia"}), 409
        
        # Chequea el total de registros para ese empleado en la fecha (máximo 2).
        g.db_cursor.execute("""
            SELECT COUNT(*) as count FROM asistencia 
            WHERE id_empleado = %s AND fecha = %s
        """, (id_empleado, fecha))
        total_registros = g.db_cursor.fetchone()['count']
        if total_registros >= 2:
            return jsonify({"error": "Máximo 2 registros por día alcanzado"}), 409
        
        # Verificación de tiempo mínimo para salida: Busca la entrada más reciente del día.
        if tipo == 'salida':
            g.db_cursor.execute("""
                SELECT hora FROM asistencia 
                WHERE id_empleado = %s AND fecha = %s AND tipo = 'entrada' 
                ORDER BY hora DESC LIMIT 1
            """, (id_empleado, fecha))
            entrada_reciente = g.db_cursor.fetchone()
            if entrada_reciente:
                hora_entrada = entrada_reciente['hora']  # Esto es timedelta.
                # Convierte timedelta a time.
                hora_entrada_time = (datetime.min + hora_entrada).time()
                # Crea datetime completo para comparar.
                entrada_datetime = datetime.combine(fecha, hora_entrada_time)
                diferencia = hora_actual - entrada_datetime
                if diferencia < timedelta(hours=2):
                    return jsonify({"error": "Hace un momento se registro, espere el minimo de tiempo para poder retirarse o comuniquese con el dueño"}), 409
        
        # Inserta en la tabla asistencia.
        query = "INSERT INTO asistencia (id_empleado, fecha, hora, tipo) VALUES (%s, %s, %s, %s)"
        g.db_cursor.execute(query, (id_empleado, fecha, hora_actual.time(), tipo))
        g.db.commit()  # Confirma la inserción.
        
        return jsonify({"mensaje": "Registro de asistencia agregado exitosamente"}), 200
    
    except Exception as e:
        g.db.rollback()  # Revierte si hay error.
        return jsonify({"error": f"Error general: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)  # Ejecuta el servidor en localhost:5000.