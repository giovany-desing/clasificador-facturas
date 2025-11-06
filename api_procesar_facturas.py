from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import sys
import os
import logging
from datetime import datetime

# Configurar path para imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from utils import conect_drive, preprocessing_data, train_model, predecir_facturas, eliminar_carpetas, connect_sql, ocr

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="Sistema de Procesamiento de Facturas",
    description="API para procesar facturas del mes en curso",
    version="1.0.0"
)

# Estado del procesamiento
processing_status = {
    "estado": "inactivo",
    "etapa_actual": None,
    "progreso": 0,
    "mensaje": None,
    "inicio": None,
    "fin": None,
    "error": None
}

# Modelos de respuesta
class ProcessingStatus(BaseModel):
    estado: str
    etapa_actual: Optional[str] = None
    progreso: int
    mensaje: Optional[str] = None
    inicio: Optional[str] = None
    fin: Optional[str] = None
    error: Optional[str] = None

class ProcessingResponse(BaseModel):
    mensaje: str
    estado: str

# Función para ejecutar el procesamiento completo en segundo plano
def ejecutar_procesamiento_completo():
    """Ejecuta todo el pipeline de procesamiento de facturas"""
    global processing_status
    
    try:
        # Actualizar estado: Iniciando
        processing_status.update({
            "estado": "ejecutando",
            "etapa_actual": "iniciando",
            "progreso": 0,
            "mensaje": "Iniciando pipeline de procesamiento de facturas",
            "inicio": datetime.now().isoformat(),
            "fin": None,
            "error": None
        })
        logger.info("Pipeline de procesamiento iniciado")
        
        # FASE 1: Descarga desde Drive
        processing_status.update({
            "etapa_actual": "descarga_drive",
            "progreso": 10,
            "mensaje": "Descargando carpeta 'mes en curso' desde Google Drive"
        })
        logger.info("Descargando carpeta 'mes en curso'")
        conect_drive.descargar_carpeta('mes en curso')
        processing_status["progreso"] = 15
        
        # FASE 2: Subir a histórico
        processing_status.update({
            "etapa_actual": "subir_historico",
            "progreso": 20,
            "mensaje": "Subiendo mes en curso a histórico"
        })
        logger.info("Subiendo a histórico")
        conect_drive.subir_mes_curso_a_historico()
        processing_status["progreso"] = 25
        
        # FASE 3: Predicción de facturas
        processing_status.update({
            "etapa_actual": "prediccion",
            "progreso": 30,
            "mensaje": "Ejecutando predicción de facturas"
        })
        logger.info("Iniciando predicción de facturas")
        predecir_facturas.predecir()
        processing_status["progreso"] = 50
        
        # FASE 4: Subir documentos
        processing_status.update({
            "etapa_actual": "subir_documentos",
            "progreso": 55,
            "mensaje": "Subiendo documentos preventivos y correctivos"
        })
        logger.info("Subiendo documentos a Drive")
        conect_drive.subir_documentos_preventivos_correctivos()
        processing_status["progreso"] = 60
        
        # FASE 5: Procesamiento OCR
        processing_status.update({
            "etapa_actual": "procesamiento_ocr",
            "progreso": 65,
            "mensaje": "Procesando facturas con OCR"
        })
        logger.info("Iniciando procesamiento OCR para correctivos")
        ocr.procesar_carpeta_facturas("corr")
        processing_status["progreso"] = 70
        
        processing_status.update({
            "mensaje": "Procesando facturas preventivas con OCR"
        })
        logger.info("Iniciando procesamiento OCR para preventivos")
        ocr.procesar_carpeta_facturas("prev")
        processing_status["progreso"] = 75
        
        # FASE 6: Limpieza local
        processing_status.update({
            "etapa_actual": "limpieza_local",
            "progreso": 80,
            "mensaje": "Eliminando carpetas temporales locales"
        })
        logger.info("Iniciando limpieza de carpetas locales")
        
        eliminar_carpetas.eliminar_carpeta_local("prev")
        processing_status["progreso"] = 82
        
        eliminar_carpetas.eliminar_carpeta_local("corr")
        processing_status["progreso"] = 84
        
        eliminar_carpetas.eliminar_carpeta_local("mes en curso")
        processing_status["progreso"] = 86
        
        logger.info("Limpieza local completada")
        
        # FASE 7: Limpieza Drive
        processing_status.update({
            "etapa_actual": "limpieza_drive",
            "progreso": 90,
            "mensaje": "Limpiando archivos en Google Drive"
        })
        logger.info("Iniciando limpieza en Google Drive")
        conect_drive.eliminar_archivos_drive(nombre_carpeta="mes en curso", horas_limite=1, eliminar_permanentemente=False)
        processing_status["progreso"] = 95
        
        # Procesamiento completado
        processing_status.update({
            "estado": "completado",
            "etapa_actual": "finalizado",
            "progreso": 100,
            "mensaje": "Procesamiento de facturas completado exitosamente",
            "fin": datetime.now().isoformat()
        })
        logger.info("Pipeline de procesamiento completado exitosamente")
        
    except Exception as e:
        error_msg = f"Error en el procesamiento: {str(e)}"
        logger.error(error_msg, exc_info=True)
        processing_status.update({
            "estado": "error",
            "mensaje": "Error durante el procesamiento",
            "error": error_msg,
            "fin": datetime.now().isoformat()
        })

# Endpoints
@app.post("/procesar_facturas", response_model=ProcessingResponse)
async def procesar_facturas_endpoint(background_tasks: BackgroundTasks):
    """
    Endpoint para iniciar el procesamiento completo de facturas
    
    Este endpoint ejecuta el pipeline completo:
    - Descarga carpeta 'mes en curso' desde Google Drive
    - Sube a histórico
    - Ejecuta predicción de facturas
    - Sube documentos preventivos/correctivos
    - Procesa OCR en las facturas
    - Limpia archivos temporales locales y en Drive
    """
    global processing_status
    
    # Verificar si ya hay un procesamiento ejecutándose
    if processing_status["estado"] == "ejecutando":
        raise HTTPException(
            status_code=409,
            detail="Ya hay un procesamiento en ejecución. Espera a que termine."
        )
    
    # Reiniciar estado
    processing_status.update({
        "estado": "en_cola",
        "etapa_actual": "pendiente",
        "progreso": 0,
        "mensaje": "Procesamiento añadido a la cola de ejecución",
        "inicio": None,
        "fin": None,
        "error": None
    })
    
    # Ejecutar procesamiento en segundo plano
    background_tasks.add_task(ejecutar_procesamiento_completo)
    
    logger.info("Procesamiento de facturas añadido a la cola de ejecución")
    
    return ProcessingResponse(
        mensaje="Procesamiento de facturas iniciado en segundo plano",
        estado="en_cola"
    )

@app.get("/procesar_facturas/status", response_model=ProcessingStatus)
async def get_processing_status():
    """
    Obtiene el estado actual del procesamiento de facturas
    """
    return ProcessingStatus(**processing_status)

@app.post("/procesar_facturas/reset")
async def reset_processing_status():
    """
    Resetea el estado del procesamiento (útil si hubo un error)
    """
    global processing_status
    
    if processing_status["estado"] == "ejecutando":
        raise HTTPException(
            status_code=409,
            detail="No se puede resetear mientras el procesamiento está ejecutándose"
        )
    
    processing_status.update({
        "estado": "inactivo",
        "etapa_actual": None,
        "progreso": 0,
        "mensaje": None,
        "inicio": None,
        "fin": None,
        "error": None
    })
    
    return {"mensaje": "Estado del procesamiento reseteado correctamente"}

@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "mensaje": "API de Procesamiento de Facturas",
        "version": "1.0.0",
        "endpoints": {
            "POST /procesar_facturas": "Iniciar procesamiento de facturas",
            "GET /procesar_facturas/status": "Obtener estado del procesamiento",
            "POST /procesar_facturas/reset": "Resetear estado del procesamiento"
        }
    }

# Para ejecutar el servidor
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)  # Puerto diferente para evitar conflicto