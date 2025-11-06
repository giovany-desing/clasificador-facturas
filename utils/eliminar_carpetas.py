# utils/script_eliminacion.py
import os
import shutil
import logging
from pathlib import Path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import log_utils
# Configurar logging
logger = log_utils.logs()

def eliminar_carpeta_local(nombre_carpeta):
    """Elimina una carpeta local y todo su contenido de forma recursiva"""
    try:
        # Obtener la ruta de la carpeta en la raíz del proyecto
        directorio_raiz = os.path.dirname(os.path.dirname(__file__))
        ruta_carpeta = os.path.join(directorio_raiz, nombre_carpeta)
        
        # Verificar si la carpeta existe
        if not os.path.exists(ruta_carpeta):
            logger.warning(f"La carpeta '{nombre_carpeta}' no existe en la ruta: {ruta_carpeta}")
            return False
        
        # Verificar que es una carpeta y no un archivo
        if not os.path.isdir(ruta_carpeta):
            logger.error(f"La ruta '{ruta_carpeta}' no es una carpeta")
            return False
        
        # Eliminar carpeta y todo su contenido recursivamente
        logger.info(f"Eliminando Carpeta '{nombre_carpeta}' ...")
        shutil.rmtree(ruta_carpeta)
        logger.info(f"✓ Carpeta '{nombre_carpeta}' eliminada exitosamente")
        return True
        
    except PermissionError as e:
        logger.error(f"Error de permisos al eliminar '{nombre_carpeta}': {e}")
        return False
    except Exception as e:
        logger.error(f"Error eliminando carpeta '{nombre_carpeta}': {e}")
        return False
                
if __name__ == "__main__":
    pass
    #eliminar_carpeta_local("mes en curso")