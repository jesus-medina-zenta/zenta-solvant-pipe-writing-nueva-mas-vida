#!/bin/bash

# Script de setup para el proyecto
set -e

echo "🚀 Configurando el proyecto znt-template-pipe-python..."

# Verificar que Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no está instalado. Por favor instala Python 3.9 o superior."
    exit 1
fi

# Verificar versión de Python
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Se requiere Python $required_version o superior. Versión actual: $python_version"
    exit 1
fi

echo "✅ Python $python_version detectado"

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "📦 Creando entorno virtual..."
    python3 -m venv venv
else
    echo "✅ Entorno virtual ya existe"
fi

# Activar entorno virtual
echo "🔧 Activando entorno virtual..."
source venv/bin/activate

# Actualizar pip
echo "⬆️ Actualizando pip..."
pip install --upgrade pip

# Instalar dependencias de producción
echo "📚 Instalando dependencias de producción..."
pip install -r requirements.txt

# Instalar dependencias de desarrollo
echo "🛠️ Instalando dependencias de desarrollo..."
pip install -r requirements-dev.txt

# Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    echo "📝 Creando archivo .env desde template..."
    cp .env.example .env
    echo "⚠️ Por favor edita el archivo .env con tus configuraciones específicas"
else
    echo "✅ Archivo .env ya existe"
fi

# Verificar que todo funciona
echo "🧪 Verificando instalación..."
python -c "
import asyncpg
import google.cloud.bigquery
import pydantic
import pandas
print('✅ Todas las dependencias principales están instaladas correctamente')
"

echo ""
echo "🎉 ¡Setup completado exitosamente!"
echo ""
echo "Próximos pasos:"
echo "1. Activa el entorno virtual: source venv/bin/activate"
echo "2. Edita el archivo .env con tus configuraciones"
echo "3. Ejecuta los tests: python -m pytest"
echo "4. Ejecuta el pipeline: python src/main.py"
echo ""
