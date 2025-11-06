import pyodbc
from typing import List
import sys
import os


from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
from utils import log_utils, connect_sql
logger = log_utils.logs()

# Configuración de conexión con variables de entorno para Docker
def get_connection_string():
    """Obtiene la cadena de conexión desde variables de entorno o usa valores por defecto"""
    server = os.getenv('SQL_SERVER', 'localhost')
    database = os.getenv('SQL_DATABASE', 'master')
    username = os.getenv('SQL_USERNAME', 'sa')
    password = os.getenv('SQL_PASSWORD', 'AzureDocking2025@')
    
    conn_str = (
        r'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password};'
    )
    return conn_str

# Cadena de conexión
conn_str = get_connection_string()

logger = log_utils.logs()

# Función para obtener conexión (mantiene compatibilidad)
def get_connection():
    """Obtiene una conexión a la base de datos"""
    try:
        cnxn = pyodbc.connect(conn_str)
        return cnxn
    except pyodbc.Error as e:
        logger.error(f"Error al conectar a la base de datos: {e}")
        return None

# Conexión global (mantiene compatibilidad con código existente)
try:
    cnxn = get_connection()
    cursor = cnxn.cursor() if cnxn else None
except pyodbc.Error as e:
    logger.error(f"Error en conexión global: {e}")
    cnxn = None
    cursor = None

#funcion para la tabla invoices
def actualizar_orden_fecha(orden_compra: int, fecha_creacion: str, productos: list, cantidades: list, totales: list, carpeta: str) -> bool:
    """
    Actualiza la orden en la tabla correspondiente según la carpeta especificada
    """
    
    # Validar que carpeta solo contenga caracteres alfanuméricos para prevenir SQL injection
    if not carpeta.isalnum():
        logger.error(f"Error: El parámetro carpeta '{carpeta}' contiene caracteres no válidos")
        return False
    
    if len(productos) != len(cantidades) or len(productos) != len(totales):
        logger.error(f"Error: Las listas de productos, cantidades y totales no coinciden")
        return False
    
    # Determinar el nombre de la tabla de forma segura
    nombre_tabla = f"invoices_{carpeta}"
    
    try:
        with pyodbc.connect(conn_str) as cnxn:
            with cnxn.cursor() as cursor:
                # Verificar si la tabla existe
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME = ?
                """, (nombre_tabla,))
                
                if cursor.fetchone()[0] == 0:
                    logger.error(f"Error: La tabla {nombre_tabla} no existe")
                    return False
                
                # Eliminar registros existentes
                query_eliminar = f'DELETE FROM {nombre_tabla} WHERE "ORDEN_DE_COMPRA" = ?'
                cursor.execute(query_eliminar, (orden_compra,))
                
                # Insertar nuevos registros
                for producto, cantidad, total in zip(productos, cantidades, totales):
                    try:
                        total_float = float(str(total).replace(',', ''))
                    except (ValueError, AttributeError):
                        logger.warning(f"No se pudo convertir el total '{total}' a float. Se usará 0.0")
                        total_float = 0.0
                    
                    query_insertar = f'''
                        INSERT INTO {nombre_tabla} ("ORDEN_DE_COMPRA", "FECHA_DE_CREACION", "PRODUCTO", "CANTIDAD", "TOTAL_PRODUCTO")
                        VALUES (?, ?, ?, ?, ?)
                    '''
                    cursor.execute(query_insertar, (orden_compra, fecha_creacion, producto, cantidad, total_float))
                
                cnxn.commit()
                logger.info(f"Orden {orden_compra} procesada en tabla {nombre_tabla}: {len(productos)} productos insertados.")
                return True
                    
    except pyodbc.Error as e:
        logger.error(f"Error de base de datos al procesar orden {orden_compra} en tabla {nombre_tabla}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al procesar orden {orden_compra} en tabla {nombre_tabla}: {e}")
        return False
    

#funcion para la tabla ord
def actualizar_orden_total(orden_compra: int, total: float, carpeta: str) -> bool:
    """
    Actualiza o inserta el total de una orden en la tabla correspondiente según la carpeta
    
    Args:
        orden_compra: Número de orden de compra
        total: Total de la orden
        carpeta: Tipo de carpeta ('prev', 'corr', etc.) que determina el nombre de la tabla
    """
    
    logger.info(f"Procesando orden en ord_{carpeta}: {orden_compra}, total: {total}")
    
    # Validar que carpeta solo contenga caracteres alfanuméricos para prevenir SQL injection
    if not carpeta.isalnum():
        logger.error(f"Error: El parámetro carpeta '{carpeta}' contiene caracteres no válidos")
        return False
    
    # Determinar el nombre de la tabla basado en el parámetro carpeta
    nombre_tabla = f"ord_{carpeta}"
    
    try:
        with pyodbc.connect(conn_str) as cnxn:
            with cnxn.cursor() as cursor:
                # Verificar si la tabla existe
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME = ?
                """, (nombre_tabla,))
                
                if cursor.fetchone()[0] == 0:
                    logger.error(f"Error: La tabla {nombre_tabla} no existe")
                    return False
                
                # Verificar si la orden ya existe usando COUNT
                cursor.execute(f'''
                    SELECT COUNT(*) FROM {nombre_tabla} 
                    WHERE "ORDEN_DE_COMPRA" = ?
                ''', (orden_compra,))
                
                existe = cursor.fetchone()[0] > 0
                
                # Convertir total a float
                try:
                    total_float = float(str(total).replace(',', ''))
                except (ValueError, AttributeError):
                    logger.warning(f"No se pudo convertir el total '{total}' a float. Se usará 0.0")
                    total_float = 0.0
                
                if existe:
                    # Si la orden YA EXISTE → ACTUALIZA
                    cursor.execute(f'''
                        UPDATE {nombre_tabla} 
                        SET "TOTAL" = ?
                        WHERE "ORDEN_DE_COMPRA" = ?
                    ''', (total_float, orden_compra))
                    cnxn.commit()
                    logger.info(f"Orden {orden_compra} actualizada en {nombre_tabla} correctamente.")
                    return True
                else:
                    # Si la orden NO EXISTE → INSERTA
                    cursor.execute(f'''
                        INSERT INTO {nombre_tabla} ("ORDEN_DE_COMPRA", "TOTAL")
                        VALUES (?, ?)
                    ''', (orden_compra, total_float))
                    cnxn.commit()
                    logger.info(f"Orden {orden_compra} insertada en {nombre_tabla} correctamente.")
                    return True
                    
    except pyodbc.Error as e:
        logger.error(f"Error de base de datos al procesar orden {orden_compra} en {nombre_tabla}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al procesar orden {orden_compra} en {nombre_tabla}: {e}")
        return Falsex