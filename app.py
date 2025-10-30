from flask import Flask, request, jsonify, g  # Agregado g para la conexión DB global.
import mysql.connector 
from datetime import datetime  # Para obtener fecha y hora actuales.
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
        id_empleado = data.get('id_empleado')  # ID del empleado (debe existir en tabla empleados).
        tipo = data.get('tipo', 'entrada')  # Tipo: 'entrada' o 'salida' (default 'entrada').
        
        if not id_empleado:
            return jsonify({"error": "Falta id_empleado"}), 400
        
        # Obtiene fecha y hora actuales.
        fecha = datetime.now().date()
        hora = datetime.now().time()
        
        # Inserta en la tabla asistencia usando g.db_cursor.
        query = "INSERT INTO asistencia (id_empleado, fecha, hora, tipo) VALUES (%s, %s, %s, %s)"
        g.db_cursor.execute(query, (id_empleado, fecha, hora, tipo))
        g.db.commit()  # Confirma la inserción.
        
        return jsonify({"mensaje": "Registro de asistencia agregado exitosamente"}), 200
    
    except Exception as e:
        g.db.rollback()  # Revierte si hay error.
        return jsonify({"error": f"Error general: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)  # Ejecuta el servidor en localhost:5000.