# utils/conect_drive.py
import shutil
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

import pickle
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive']

import os
import sys
import io
import logging
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import log_utils

# Configurar logging
logger = log_utils.logs()




def autenticar_drive():
    """
    Autentica con Google Drive usando Service Account (completamente automático)
    
    Returns:
        googleapiclient.discovery.Resource: Servicio de Google Drive autenticado
        
    Raises:
        FileNotFoundError: Si no se encuentra el archivo de credenciales
        ValueError: Si el archivo de credenciales es inválido
        Exception: Para otros errores de autenticación
    """
    service_account_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'service-account-key.json'
    )
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    try:
        if not os.path.exists(service_account_path):
            logger.error(f"Archivo de credenciales no encontrado en: {service_account_path}")
            raise FileNotFoundError(
                f"No se encontró el archivo 'service-account-key.json' en {service_account_path}. "
                "Por favor, descarga las credenciales de la Service Account desde Google Cloud Console."
            )
        
        logger.info(f"Cargando credenciales desde: {service_account_path}")
        
        try:
            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=SCOPES
            )
            logger.info("Credenciales de Service Account cargadas exitosamente")
        except ValueError as e:
            logger.error(f"Archivo de credenciales inválido: {e}")
            raise ValueError(
                f"El archivo 'service-account-key.json' no es válido o está corrupto. "
                f"Error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error al cargar credenciales: {e}")
            raise Exception(f"Error inesperado al cargar credenciales: {str(e)}")
        
        try:
            drive_service = build('drive', 'v3', credentials=credentials)
            logger.info("Servicio de Google Drive construido exitosamente")
        except HttpError as e:
            logger.error(f"Error HTTP al construir servicio de Drive: {e}")
            raise Exception(
                f"Error al conectar con Google Drive API. "
                f"Verifica que la API esté habilitada en Google Cloud Console. Error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error al construir servicio de Drive: {e}")
            raise Exception(f"Error inesperado al construir servicio de Drive: {str(e)}")
        
        try:
            logger.debug("Verificando autenticación con Google Drive...")
            about = drive_service.about().get(fields="user").execute()
            user_email = about.get('user', {}).get('emailAddress', 'Desconocido')
            logger.info(f"Autenticación exitosa. Service Account: {user_email}")
        except HttpError as e:
            if e.resp.status == 403:
                logger.error("Permiso denegado. Verifica que la API de Drive esté habilitada")
                raise Exception(
                    "Acceso denegado a Google Drive API. "
                    "Asegúrate de que la API de Google Drive esté habilitada en tu proyecto de Google Cloud."
                )
            else:
                logger.warning(f"No se pudo verificar la autenticación: {e}")
        except Exception as e:
            logger.warning(f"No se pudo verificar la autenticación (no crítico): {e}")
        
        logger.info("Autenticación con Google Drive completada exitosamente")
        return drive_service
        
    except (FileNotFoundError, ValueError) as e:
        raise
    except Exception as e:
        logger.critical(f"Error crítico durante la autenticación con Google Drive: {e}")
        raise Exception(f"Fallo en autenticación con Google Drive: {str(e)}")


def _buscar_carpeta_por_nombre(drive, nombre_carpeta, parent_id='root'):
    """
    Busca una carpeta por nombre en Drive (función auxiliar interna)
    
    Args:
        drive: Servicio de Google Drive autenticado
        nombre_carpeta: Nombre de la carpeta a buscar
        parent_id: ID de la carpeta padre (si es 'root', busca en todas partes)
        
    Returns:
        str: ID de la carpeta encontrada o None
    """
    try:
        # Si parent_id es 'root', buscar en todas las carpetas compartidas
        if parent_id == 'root':
            query = f"name='{nombre_carpeta}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            logger.debug(f"Buscando carpeta '{nombre_carpeta}' en todas las ubicaciones")
        else:
            query = f"name='{nombre_carpeta}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            logger.debug(f"Buscando carpeta '{nombre_carpeta}' dentro de parent_id: {parent_id}")
        
        logger.debug(f"Query: {query}")
        
        results = drive.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, parents)',
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        folders = results.get('files', [])
        
        if not folders:
            logger.warning(f"No se encontró la carpeta '{nombre_carpeta}'")
            logger.info("💡 Asegúrate de compartir la carpeta con el email de la Service Account")
            return None
        
        if len(folders) > 1:
            logger.warning(f"Se encontraron {len(folders)} carpetas con nombre '{nombre_carpeta}', usando la primera")
            for i, folder in enumerate(folders):
                logger.debug(f"  Carpeta {i+1}: ID={folder['id']}, Parents={folder.get('parents', 'N/A')}")
        
        folder_id = folders[0]['id']
        logger.info(f"Carpeta '{nombre_carpeta}' encontrada con ID: {folder_id}")
        return folder_id
        
    except HttpError as e:
        logger.error(f"Error HTTP al buscar carpeta '{nombre_carpeta}': {e}")
        if e.resp.status == 403:
            logger.error("❌ Acceso denegado. Verifica que la carpeta esté compartida con la Service Account")
        return None
    except Exception as e:
        logger.error(f"Error al buscar carpeta '{nombre_carpeta}': {e}")
        return None


def _listar_archivos_en_carpeta(drive, folder_id, incluir_carpetas=False):
    """
    Lista archivos en una carpeta (función auxiliar interna)
    
    Args:
        drive: Servicio de Google Drive autenticado
        folder_id: ID de la carpeta
        incluir_carpetas: Si True, incluye subcarpetas en el resultado
        
    Returns:
        list: Lista de archivos/carpetas con metadatos
    """
    try:
        if incluir_carpetas:
            query = f"'{folder_id}' in parents and trashed=false"
        else:
            query = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        
        logger.debug(f"Listando archivos en carpeta ID: {folder_id}")
        
        all_files = []
        page_token = None
        
        while True:
            results = drive.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType, size, modifiedTime, createdTime)',
                pageSize=100,
                pageToken=page_token
            ).execute()
            
            files = results.get('files', [])
            all_files.extend(files)
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        
        logger.debug(f"Se encontraron {len(all_files)} elementos en la carpeta")
        return all_files
        
    except Exception as e:
        logger.error(f"Error al listar archivos: {e}")
        return []


def _descargar_archivo(drive, file_id, destination_path):
    """
    Descarga un archivo desde Drive (función auxiliar interna)
    
    Args:
        drive: Servicio de Google Drive autenticado
        file_id: ID del archivo a descargar
        destination_path: Ruta local donde guardar el archivo
        
    Returns:
        bool: True si la descarga fue exitosa
    """
    try:
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        request = drive.files().get_media(fileId=file_id)
        
        with io.FileIO(destination_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.debug(f"Descarga {progress}%: {os.path.basename(destination_path)}")
        
        logger.debug(f"Archivo descargado: {os.path.basename(destination_path)}")
        return True
        
    except Exception as e:
        logger.error(f"Error al descargar archivo {file_id}: {e}")
        return False


def descargar_carpeta_recursiva(drive, folder_id, ruta_local):
    """Descarga recursivamente el contenido de una carpeta de Google Drive"""
    try:
        # Listar todos los elementos (archivos y carpetas)
        elementos = _listar_archivos_en_carpeta(drive, folder_id, incluir_carpetas=True)
        
        if not elementos:
            logger.debug(f"Carpeta vacía: {ruta_local}")
            return True
        
        # Separar archivos y carpetas
        archivos = [e for e in elementos if e.get('mimeType') != 'application/vnd.google-apps.folder']
        carpetas = [e for e in elementos if e.get('mimeType') == 'application/vnd.google-apps.folder']
        
        # Descargar archivos
        for archivo in archivos:
            try:
                ruta_archivo = os.path.join(ruta_local, archivo['name'])
                logger.debug(f"Descargando archivo: {archivo['name']}")
                _descargar_archivo(drive, archivo['id'], ruta_archivo)
            except Exception as e:
                logger.error(f"Error descargando archivo {archivo['name']}: {e}")
        
        # Procesar subcarpetas recursivamente
        for carpeta in carpetas:
            ruta_subcarpeta = os.path.join(ruta_local, carpeta['name'])
            os.makedirs(ruta_subcarpeta, exist_ok=True)
            descargar_carpeta_recursiva(drive, carpeta['id'], ruta_subcarpeta)
        
        return True
        
    except Exception as e:
        logger.error(f"Error en descarga recursiva: {e}")
        return False


def descargar_carpeta(nombre_carpeta):
    """Descarga una carpeta específica de Google Drive a la raíz del proyecto"""
    try:
        logger.info(f"Iniciando descarga de carpeta: {nombre_carpeta}")
        drive = autenticar_drive()
        
        # Buscar carpeta principal de facturas
        FOLDER_NAME = 'facturas'
        
        logger.info(f"Buscando carpeta principal: {FOLDER_NAME}")
        folder_id = _buscar_carpeta_por_nombre(drive, FOLDER_NAME)

        if not folder_id:
            logger.error(f"No se encontró la carpeta principal '{FOLDER_NAME}'")
            return False

        ID_CARPETA_PRINCIPAL = folder_id
        logger.info(f"Carpeta principal '{FOLDER_NAME}' encontrada. ID: {ID_CARPETA_PRINCIPAL}")
        logger.info(f"Descargando documentos ...")
        
        # Buscar carpeta específica
        logger.info(f"Buscando carpeta: {nombre_carpeta}")
        carpeta_id = _buscar_carpeta_por_nombre(drive, nombre_carpeta, ID_CARPETA_PRINCIPAL)
        
        if not carpeta_id:
            logger.error(f"No se encontró la carpeta '{nombre_carpeta}'")
            return False
            
        logger.info(f"Carpeta '{nombre_carpeta}' encontrada. ID: {carpeta_id}")
        
        # Crear directorio en la raíz del proyecto
        directorio_raiz = os.path.dirname(os.path.dirname(__file__))
        ruta_destino = os.path.join(directorio_raiz, nombre_carpeta)
        
        # Crear directorio si no existe
        os.makedirs(ruta_destino, exist_ok=True)
        
        # Descargar contenido recursivo de la carpeta
        if descargar_carpeta_recursiva(drive, carpeta_id, ruta_destino):
            logger.info(f"✓ Carpeta '{nombre_carpeta}' descargada exitosamente en: {ruta_destino}")
            return True
        else:
            logger.error(f"✗ Error al descargar carpeta '{nombre_carpeta}'")
            return False

    except Exception as e:
        logger.error(f"Error descargando carpeta '{nombre_carpeta}': {e}", exc_info=True)
        return False


def eliminar_archivos_drive(nombre_carpeta="mes en curso", horas_limite=1, eliminar_permanentemente=False):
    """
    Versión más flexible para eliminar archivos por antigüedad
    
    Args:
        nombre_carpeta (str): Nombre de la carpeta dentro de 'facturas'
        horas_limite (int): Eliminar archivos más recientes que X horas
        eliminar_permanentemente (bool): Si es True, elimina permanentemente en lugar de enviar a papelera
    """
    try:
        logger.info(f"🔍 Eliminando archivos de '{nombre_carpeta}' con menos de {horas_limite} hora(s)")
        drive = autenticar_drive()
        
        # Buscar carpeta principal
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        if not carpeta_principal_id:
            logger.error("No se encontró la carpeta principal 'facturas'")
            return False
        
        # Buscar carpeta target
        carpeta_target_id = _buscar_carpeta_por_nombre(drive, nombre_carpeta, carpeta_principal_id)
        if not carpeta_target_id:
            logger.error(f"No se encontró la carpeta '{nombre_carpeta}'")
            return False
        
        # Listar archivos
        archivos = _listar_archivos_en_carpeta(drive, carpeta_target_id)
        
        if not archivos:
            logger.info(f"No hay archivos en la carpeta '{nombre_carpeta}'")
            return True
        
        # Calcular límite de tiempo
        hora_limite = datetime.now(timezone.utc) - timedelta(hours=horas_limite)
        
        logger.info(f"⏰ Límite temporal: {hora_limite.strftime('%Y-%m-%d %H:%M:%S')}")
        
        archivos_eliminados = 0
        
        # Procesar archivos
        for archivo in archivos:
            try:
                # Parsear fecha de creación
                fecha_creacion_str = archivo.get('createdTime')
                if not fecha_creacion_str:
                    logger.warning(f"Archivo sin fecha de creación: {archivo['name']}")
                    continue
                
                fecha_creacion = datetime.fromisoformat(fecha_creacion_str.replace('Z', '+00:00'))
                
                if fecha_creacion > hora_limite:
                    if eliminar_permanentemente:
                        # Eliminar permanentemente
                        drive.files().delete(fileId=archivo['id']).execute()
                        logger.info(f"🗑️  ELIMINADO PERMANENTEMENTE: {archivo['name']}")
                    else:
                        # Enviar a papelera (actualizar con trashed=true)
                        drive.files().update(
                            fileId=archivo['id'],
                            body={'trashed': True}
                        ).execute()
                        logger.info(f"🗑️  ENVIADO A PAPELERA: {archivo['name']}")
                    
                    archivos_eliminados += 1
                    
            except Exception as e:
                logger.error(f"Error procesando archivo {archivo.get('name', 'desconocido')}: {e}")
                continue
        
        logger.info(f"✅ Total archivos eliminados: {archivos_eliminados}")
        return True
        
    except Exception as e:
        logger.error(f"Error en eliminar_archivos_drive: {e}", exc_info=True)
        return False


def buscar_o_crear_carpeta(drive, carpeta_padre_id, nombre_carpeta):
    """
    Busca una carpeta en Drive y si no existe, la crea
    """
    try:
        # Buscar carpeta existente
        carpeta_id = _buscar_carpeta_por_nombre(drive, nombre_carpeta, carpeta_padre_id)
        
        if carpeta_id:
            logger.debug(f"✅ Carpeta '{nombre_carpeta}' encontrada en Drive")
            return {'id': carpeta_id}
        else:
            # Crear nueva carpeta
            logger.info(f"📁 Creando nueva carpeta: '{nombre_carpeta}'")
            
            file_metadata = {
                'name': nombre_carpeta,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [carpeta_padre_id]
            }
            
            folder = drive.files().create(
                body=file_metadata,
                fields='id, name'
            ).execute()
            
            logger.info(f"✅ Carpeta '{nombre_carpeta}' creada exitosamente. ID: {folder['id']}")
            return folder
            
    except Exception as e:
        logger.error(f"❌ Error buscando/creando carpeta '{nombre_carpeta}': {e}")
        return None


def subir_documentos_preventivos_correctivos():
    """
    Sube documentos desde carpetas locales 'prev' y 'corr' a Google Drive
    - 'prev' → 'preventivos' en Drive  
    - 'corr' → 'correctivos' en Drive
    """
    try:
        logger.info("🚀 Iniciando subida de documentos preventivos y correctivos")
        drive = autenticar_drive()
        
        # Obtener ruta raíz del proyecto
        directorio_raiz = os.path.dirname(os.path.dirname(__file__))
        
        # Buscar carpeta principal 'facturas' en Drive
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        
        if not carpeta_principal_id:
            logger.error("❌ No se encontró la carpeta principal 'facturas' en Drive")
            return False

        ID_CARPETA_PRINCIPAL = carpeta_principal_id
        logger.info(f"✅ Carpeta principal 'facturas' encontrada. ID: {ID_CARPETA_PRINCIPAL}")
        
        # Configuración de carpetas a procesar
        carpetas_procesar = [
            {
                'local': 'prev',
                'drive': 'preventivos', 
                'tipo': 'PREVENTIVOS'
            },
            {
                'local': 'corr', 
                'drive': 'correctivos',
                'tipo': 'CORRECTIVOS'
            }
        ]
        
        resultados = []
        
        for config in carpetas_procesar:
            carpeta_local = os.path.join(directorio_raiz, config['local'])
            nombre_carpeta_drive = config['drive']
            tipo = config['tipo']
            
            logger.info(f"📤 Procesando {tipo}...")
            
            # Verificar que existe la carpeta local
            if not os.path.exists(carpeta_local):
                logger.error(f"❌ No existe la carpeta local: {carpeta_local}")
                resultados.append(False)
                continue
            
            # Buscar o crear carpeta en Drive
            carpeta_drive = buscar_o_crear_carpeta(drive, ID_CARPETA_PRINCIPAL, nombre_carpeta_drive)
            if not carpeta_drive:
                logger.error(f"❌ No se pudo obtener/crear carpeta '{nombre_carpeta_drive}' en Drive")
                resultados.append(False)
                continue
            
            # Obtener lista de archivos en carpeta local
            archivos_local = []
            extensiones_validas = ['.pdf', '.jpg', '.jpeg', '.png', '.txt', '.doc', '.docx', '.xls', '.xlsx']
            
            try:
                for archivo in os.listdir(carpeta_local):
                    ruta_completa = os.path.join(carpeta_local, archivo)
                    if os.path.isfile(ruta_completa):
                        _, extension = os.path.splitext(archivo)
                        if extension.lower() in extensiones_validas:
                            archivos_local.append(ruta_completa)
                        else:
                            logger.debug(f"⏭️  Archivo omitido (extensión no válida): {archivo}")
            except Exception as e:
                logger.error(f"❌ Error obteniendo archivos de {carpeta_local}: {e}")
                resultados.append(False)
                continue
            
            if not archivos_local:
                logger.info(f"📭 No hay archivos para subir en {carpeta_local}")
                resultados.append(True)
                continue
            
            logger.info(f"📄 Encontrados {len(archivos_local)} archivos en {carpeta_local}")
            
            # Subir cada archivo
            archivos_subidos = 0
            for archivo_path in archivos_local:
                try:
                    nombre_archivo = os.path.basename(archivo_path)
                    
                    # Crear metadata del archivo en Drive
                    file_metadata = {
                        'name': nombre_archivo,
                        'parents': [carpeta_drive['id']]
                    }
                    
                    media = MediaFileUpload(archivo_path, resumable=True)
                    
                    file = drive.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, name'
                    ).execute()
                    
                    archivos_subidos += 1
                    logger.debug(f"✅ Subido: {nombre_archivo}")
                    
                except Exception as e:
                    logger.error(f"❌ Error subiendo {os.path.basename(archivo_path)}: {e}")
                    continue
            
            logger.info(f"🎯 {tipo}: {archivos_subidos}/{len(archivos_local)} archivos subidos exitosamente")
            resultados.append(archivos_subidos > 0)
        
        # Resumen final
        exitos = sum(1 for r in resultados if r)
        total = len(resultados)
        
        logger.info("📊 RESUMEN FINAL:")
        logger.info(f"   ✅ Carpetas procesadas exitosamente: {exitos}/{total}")
        
        for i, config in enumerate(carpetas_procesar):
            estado = "✅ ÉXITO" if resultados[i] else "❌ FALLO"
            logger.info(f"   {estado} - {config['tipo']} ({config['local']} → {config['drive']})")
        
        return exitos > 0

    except Exception as e:
        logger.error(f"❌ Error crítico en subida de documentos: {e}", exc_info=True)
        return False


def subir_mes_curso_a_historico():
    """
    Sube el contenido de la carpeta local 'mes en curso' a Google Drive
    en la carpeta 'historico' dentro de 'facturas'
    """
    try:
        logger.info("📅 Iniciando subida de 'mes en curso' a 'historico'")
        drive = autenticar_drive()
        
        # Obtener ruta raíz del proyecto
        directorio_raiz = os.path.dirname(os.path.dirname(__file__))
        
        # Buscar carpeta principal 'facturas' en Drive
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        
        if not carpeta_principal_id:
            logger.error("❌ No se encontró la carpeta principal 'facturas' en Drive")
            return False

        ID_CARPETA_PRINCIPAL = carpeta_principal_id
        logger.info(f"✅ Carpeta principal 'facturas' encontrada. ID: {ID_CARPETA_PRINCIPAL}")
        
        # Buscar carpeta local 'mes en curso'
        carpeta_mes_curso_local = os.path.join(directorio_raiz, 'mes en curso')
        
        if not os.path.exists(carpeta_mes_curso_local):
            logger.error(f"❌ No existe la carpeta local: {carpeta_mes_curso_local}")
            return False
        
        # Buscar o crear carpeta 'historico' en Drive
        carpeta_historico_drive = buscar_o_crear_carpeta(drive, ID_CARPETA_PRINCIPAL, 'historico')
        if not carpeta_historico_drive:
            logger.error("❌ No se pudo obtener/crear carpeta 'historico' en Drive")
            return False
        
        # Obtener lista de archivos en carpeta local 'mes en curso'
        archivos_local = []
        extensiones_validas = ['.pdf', '.jpg', '.jpeg', '.png', '.txt', '.doc', '.docx', '.xls', '.xlsx']
        
        try:
            for archivo in os.listdir(carpeta_mes_curso_local):
                ruta_completa = os.path.join(carpeta_mes_curso_local, archivo)
                if os.path.isfile(ruta_completa):
                    _, extension = os.path.splitext(archivo)
                    if extension.lower() in extensiones_validas:
                        archivos_local.append(ruta_completa)
                    else:
                        logger.debug(f"⏭️  Archivo omitido (extensión no válida): {archivo}")
        except Exception as e:
            logger.error(f"❌ Error obteniendo archivos de {carpeta_mes_curso_local}: {e}")
            return False
        
        if not archivos_local:
            logger.info(f"📭 No hay archivos para subir en {carpeta_mes_curso_local}")
            return True
        
        logger.info(f"📄 Encontrados {len(archivos_local)} archivos en 'mes en curso'")
        
        # Subir cada archivo
        archivos_subidos = 0
        for archivo_path in archivos_local:
            try:
                nombre_archivo = os.path.basename(archivo_path)
                
                # Crear metadata del archivo en Drive
                file_metadata = {
                    'name': nombre_archivo,
                    'parents': [carpeta_historico_drive['id']]
                }
                
                media = MediaFileUpload(archivo_path, resumable=True)
                
                file = drive.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name'
                ).execute()
                
                archivos_subidos += 1
                logger.info(f"✅ Subido a histórico: {nombre_archivo}")
                
            except Exception as e:
                logger.error(f"❌ Error subiendo {os.path.basename(archivo_path)}: {e}")
                continue
        
        logger.info(f"🎯 HISTÓRICO: {archivos_subidos}/{len(archivos_local)} archivos subidos exitosamente")
        return archivos_subidos > 0

    except Exception as e:
        logger.error(f"❌ Error crítico en subida a histórico: {e}", exc_info=True)
        return False

def verificar_acceso_carpetas():
    """Función para verificar acceso a las carpetas necesarias"""
    try:
        logger.info("🔍 Verificando acceso a carpetas en Google Drive...")
        drive = autenticar_drive()
        
        # Buscar carpeta principal
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        
        if not carpeta_principal_id:
            logger.error("❌ No se encontró la carpeta 'facturas'")
            logger.info("💡 Asegúrate de:")
            logger.info("   1. Crear una carpeta llamada 'facturas' en tu Google Drive")
            logger.info("   2. Compartirla con el email de la Service Account")
            logger.info("   3. Dar permisos de 'Editor'")
            return False
        
        logger.info("✅ Carpeta 'facturas' encontrada y accesible")
        
        # Verificar subcarpetas
        subcarpetas = ['invoices_train', 'invoices_test', 'mes en curso', 'preventivos', 'correctivos', 'historico']
        
        for carpeta in subcarpetas:
            carpeta_id = _buscar_carpeta_por_nombre(drive, carpeta, carpeta_principal_id)
            if carpeta_id:
                logger.info(f"   ✅ {carpeta}: ENCONTRADA")
            else:
                logger.warning(f"   ⚠️  {carpeta}: NO ENCONTRADA (puedes crearla después)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verificando acceso: {e}")
        return False

# Ejemplos de uso
if __name__ == "__main__":
    pass
    # Descargar una carpeta invoices_train
    #descargar_carpeta('invoices_train')
    
    #Descargar otra carpeta invoices_test
    #descargar_carpeta('invoices_test')
    
    #  Descargar mes en curso
    #descargar_carpeta('mes en curso')
    
    # Descargar múltiples carpetas
    #descargar_varias_carpetas(['invoices_train', 'invoices_test'])

    #Descargar una carpeta invoices_train
    #eliminar_carpeta_local('invoices_train')

    #Descargar una carpeta invoices_test
    #eliminar_carpeta_local('invoices_test')

    #eliminar_archivos_drive(nombre_carpeta="mes en curso", horas_limite=1, eliminar_permanentemente=False)
    #subir_documentos_preventivos_correctivos()
    #subir_mes_curso_a_historico()