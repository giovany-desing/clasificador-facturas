from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import sys
import os
import logging
from datetime import datetime

# Configurar path para imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from utils import conect_drive, preprocessing_data, train_model, eliminar_carpetas

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="Sistema de Entrenamiento de Modelo de Facturas",
    description="API para entrenar modelo de clasificación de facturas",
    version="1.0.0"
)

# Estado del entrenamiento
training_status = {
    "estado": "inactivo",
    "etapa_actual": None,
    "progreso": 0,
    "mensaje": None,
    "inicio": None,
    "fin": None,
    "error": None
}

# Modelos de respuesta
class TrainingStatus(BaseModel):
    estado: str
    etapa_actual: Optional[str] = None
    progreso: int
    mensaje: Optional[str] = None
    inicio: Optional[str] = None
    fin: Optional[str] = None
    error: Optional[str] = None

class TrainingResponse(BaseModel):
    mensaje: str
    estado: str

# Función para ejecutar el entrenamiento completo en segundo plano
def ejecutar_entrenamiento_completo():
    """Ejecuta todo el pipeline de entrenamiento"""
    global training_status
    
    try:
        # Actualizar estado: Iniciando
        training_status.update({
            "estado": "ejecutando",
            "etapa_actual": "iniciando",
            "progreso": 0,
            "mensaje": "Iniciando pipeline de entrenamiento",
            "inicio": datetime.now().isoformat(),
            "fin": None,
            "error": None
        })
        logger.info("Pipeline de entrenamiento iniciado")
        
        # FASE 1: Descarga desde Drive
        training_status.update({
            "etapa_actual": "descarga_drive",
            "progreso": 10,
            "mensaje": "Descargando datos desde Google Drive"
        })
        logger.info("Iniciando descarga desde Drive")
        
        conect_drive.descargar_carpeta('invoices_test')
        training_status["progreso"] = 20
        
        conect_drive.descargar_carpeta('invoices_train')
        training_status["progreso"] = 30
        
        logger.info("Descarga desde Drive completada")
        
        # FASE 2: Preprocesamiento
        training_status.update({
            "etapa_actual": "preprocesamiento",
            "progreso": 40,
            "mensaje": "Preprocesando datos de entrenamiento y prueba"
        })
        logger.info("Iniciando preprocesamiento de datos")
        
        X_entrenamiento, y_entrenamiento, X_prueba, y_prueba = preprocessing_data.ejecutar_preprocesamiento_completo()
        training_status["progreso"] = 60
        
        training_status.update({
            "mensaje": "Guardando datos preprocesados"
        })
        preprocessing_data.guardar_datos_preprocesados_preprocesamiento(
            X_entrenamiento, y_entrenamiento, X_prueba, y_prueba
        )
        training_status["progreso"] = 70
        
        logger.info(f"Preprocesamiento completado: {len(X_entrenamiento)} imágenes de entrenamiento")
        
        # FASE 3: Entrenamiento del modelo
        training_status.update({
            "etapa_actual": "entrenamiento",
            "progreso": 80,
            "mensaje": "Entrenando modelo de red neuronal"
        })
        logger.info("Iniciando entrenamiento del modelo")
        
        train_model.entrenar_modelo()
        training_status["progreso"] = 90
        
        logger.info("Entrenamiento del modelo completado")

        # FASE 4: Limpieza
        training_status.update({
            "etapa_actual": "limpieza",
            "progreso": 95,
            "mensaje": "Eliminando archivos temporales"
        })
        logger.info("Iniciando limpieza de archivos temporales")
        
        eliminar_carpetas.eliminar_carpeta_local("invoices_test")
        eliminar_carpetas.eliminar_carpeta_local("invoices_train")
        eliminar_carpetas.eliminar_carpeta_local("train_data")
        
        training_status["progreso"] = 100
        
        # Entrenamiento completado
        training_status.update({
            "estado": "completado",
            "etapa_actual": "finalizado",
            "mensaje": "Entrenamiento completado exitosamente",
            "fin": datetime.now().isoformat()
        })
        logger.info("Pipeline de entrenamiento completado exitosamente")
        
    except Exception as e:
        error_msg = f"Error en el entrenamiento: {str(e)}"
        logger.error(error_msg, exc_info=True)
        training_status.update({
            "estado": "error",
            "mensaje": "Error durante la ejecución",
            "error": error_msg,
            "fin": datetime.now().isoformat()
        })

# Endpoints
@app.post("/train_model", response_model=TrainingResponse)
async def train_model_endpoint(background_tasks: BackgroundTasks):
    """
    Endpoint para iniciar el entrenamiento completo del modelo
    
    Este endpoint ejecuta el pipeline completo:
    - Descarga datos desde Google Drive (invoices_test, invoices_train)
    - Preprocesa las imágenes
    - Entrena el modelo de red neuronal
    - Elimina archivos temporales
    """
    global training_status
    
    # Verificar si ya hay un entrenamiento ejecutándose
    if training_status["estado"] == "ejecutando":
        raise HTTPException(
            status_code=409,
            detail="Ya hay un entrenamiento en ejecución. Espera a que termine."
        )
    
    # Reiniciar estado
    training_status.update({
        "estado": "en_cola",
        "etapa_actual": "pendiente",
        "progreso": 0,
        "mensaje": "Entrenamiento añadido a la cola de ejecución",
        "inicio": None,
        "fin": None,
        "error": None
    })
    
    # Ejecutar entrenamiento en segundo plano
    background_tasks.add_task(ejecutar_entrenamiento_completo)
    
    logger.info("Entrenamiento añadido a la cola de ejecución")
    
    return TrainingResponse(
        mensaje="Entrenamiento iniciado en segundo plano",
        estado="en_cola"
    )

@app.get("/train_model/status", response_model=TrainingStatus)
async def get_training_status():
    """
    Obtiene el estado actual del entrenamiento
    """
    return TrainingStatus(**training_status)

@app.post("/train_model/reset")
async def reset_training_status():
    """
    Resetea el estado del entrenamiento (útil si hubo un error)
    """
    global training_status
    
    if training_status["estado"] == "ejecutando":
        raise HTTPException(
            status_code=409,
            detail="No se puede resetear mientras el entrenamiento está ejecutándose"
        )
    
    training_status.update({
        "estado": "inactivo",
        "etapa_actual": None,
        "progreso": 0,
        "mensaje": None,
        "inicio": None,
        "fin": None,
        "error": None
    })
    
    return {"mensaje": "Estado del entrenamiento reseteado correctamente"}

@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "mensaje": "API de Entrenamiento de Modelo de Facturas",
        "version": "1.0.0",
        "endpoints": {
            "POST /train_model": "Iniciar entrenamiento del modelo",
            "GET /train_model/status": "Obtener estado del entrenamiento",
            "POST /train_model/reset": "Resetear estado del entrenamiento"
        }
    }

# Para ejecutar el servidor
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)