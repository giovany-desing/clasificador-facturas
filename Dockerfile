FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    poppler-utils \
    libpoppler-dev \
    unixodbc-dev \
    apt-transport-https \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requisitos primero (para mejor caching)
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# --- INICIO SOLUCIÓN ODBC ---
# 1. Importar la clave GPG de Microsoft usando gpg (Método Moderno)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg

# 2. Agregar el repositorio de Debian referenciando la clave gpg
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/mssql-release.list

# 3. Actualizar e instalar el driver 17
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17
# --- FIN SOLUCIÓN ODBC ---

# Copiar el código de la aplicación
COPY . .

# Crear directorios necesarios
RUN mkdir -p models utils

# Exponer puertos para las APIs
EXPOSE 8002 8003

# Comando por defecto (puedes cambiar según necesites)
CMD ["python", "api_train_pipeline.py"]