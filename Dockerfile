
# ------------------------
# Etapa 1: Build
# ------------------------
# Stage de compilación (build stage)
FROM python:3.12-slim AS builder

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia los archivos de definición de dependencias y los instala
# Utiliza .dockerignore para excluir archivos innecesarios
COPY requirements.txt .

# Instalar TODAS las dependencias (incluyendo dev) para build
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente necesario
COPY src ./src/

# ------------------------
# Etapa 2: Producción
# ------------------------
# Stage de Producción (production stage)
FROM python:3.12-slim

# Establecemos el directorio de trabajo
WORKDIR /app

# Copiamos las dependencias instaladas desde la etapa de construcción
# Esto copia solo lo esencial para ejecutar la aplicación, no todas las herramientas de construcción.
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# Copiamos el resto de los archivos de la aplicación desde la etapa de construcción
COPY --from=builder /app .

# Exponemos el puerto en el que correrá la aplicación (ejemplo para una app web)
EXPOSE 3000

# Cambiar al usuario no root
USER appuser

# Comando por defecto
CMD ["python", "src/main.py"]