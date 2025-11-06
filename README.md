CLASIFICADOR DE FACTURAS PDF EN GOOGLE DRIVE Y RECONOCIMIENTO OPTICO DE CARACTERES.


¿QUE HACE ESTE PROYECTO? clasifica facturas en formato PDF para una empresa textil en google drive en dos categorias, "correctivas" = 0, "preventivas" = 1, luego de la clasificacion las organiza en drive por carpetas y finalmente un OCR (Reconocimiento optico de caracteres) extrae informacion clave de estas, como orden de compra, productos vendidos, fechas etc.. y las ingresa a una base de datos SQLSERVER para luego analizarla mediante un tablero de estadisticas POWER BI, en pocas palabras es un ETL, (Extrae, Transforma y carga) informacion

¿QUE PROBLEMA SOLUCIONA? automatiza complemtamente la clasificacion, organizacion de facturas en google drive y asi mismo la extraccion de informacion clave para el area comercial esto para llevar seguimiento del comportamiento de las ventas a nivel de organizacion mediante tableros analiticos, el proceso es completamente automatizado y no requiere intervension humana.

¿COMO FUNCIONA? un job en cloud scheduler de google sera el encargado de activar cada hora el endpoint donde esta la red neuronal este job activara todo el pipeline para clasificar las facturas, organizarlas en drive, extraer informacion y luego insertarla al sqlserver

El proyecto esta orquestado para que el proceso de entrenamiento y clasificacion de facturas sea completamente automatizado 

DISTRIBUCION DE ARCHIVOS


Clasificador facturas
   │
   │
 utils -->> Es la carpeta donde estan almacenados las funciones en python encargadas de orquestar el flujo
   │
   │---__init__.py -->> para la importacion de funciones entre archivos
   │
   │---conect_drive.py -->> archivo encargado de realizar la conexion a google drive y gestionar las carpetas de drive
   │
   │---connect_sql.py  -->> archivo encargado de realizar la conexion al sql server e ingresar la informacion
   │
   │---eliminar_carpetas.py --->> encargado de eliminar las carpetas temporales que se crear en la ejecucion de los pipelines
   │
   │---logs_utils.py -->> encargado de gestion de los para la depuracion y pruebas de los scripts
   │
   │---ocr.py -->> encargado de extraer la informacion de las facturas y con el archivo connect_sql.py ingresar la info a la db
   │
   │---predecir_facturas.py -->> archivo encargado de la prediccion o clasificacion de las facturas
   │
   │---preprocessing_data.py -->> encargado del preprocesamiento de la informacion tanto para la clasificacion como para el train
   │
   │---train_model -->> encargado del entrenamiento de la red neuronal
   │
   │
.dockerignore -->> archivo docker evita que Docker copie archivos pesados, temporales o innecesarios al construir la imagen.
   │
   │
.gitignore -->> archivo git para que al momento de hacer pull y push ignore archivos y carpetas inecesarias
   │
   │
Dockerfile -->> crea una imagen de Docker preparada para ejecutar la la aplicacio de clasificador de facturas de Python
   │
   │
docker-compose.yml -->> archivo encargado de levantar los contenedores de las apis de procesar facturas y de entrenar modelo
   │
   │
api_procesar_facturas.py -->> pipeline encargado de procesar las facturas (predice la factura, la organiza en carpetas de drive y extrae la informacion para la base de datos sqlserve)
   │
   │
api_train_pipeline.py -->> pipeline de entrenamiento del modelo en caso de que se requiera


MANUAL DE DESPLIEGUE:

# Configurar el proyecto de GCP
gcloud config set project TU_PROJECT_ID

# Autenticar Docker con GCR
gcloud auth configure-docker

# Construir la imagen
docker build -t gcr.io/TU_PROJECT_ID/clasificador-facturas:latest .

# Subir la imagen
docker push gcr.io/TU_PROJECT_ID/clasificador-facturas:latest

# DESPLEGAR
gcloud run deploy clasificador-facturas \
  --image gcr.io/TU_PROJECT_ID/clasificador-facturas:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars "DB_HOST=TU_DB_HOST,DB_PORT=3306,DB_NAME=TU_DB,DB_USER=TU_USER" \
  --set-secrets "DB_PASSWORD=db-password:latest" \
  --min-instances 0 \
  --max-instances 10




   

 