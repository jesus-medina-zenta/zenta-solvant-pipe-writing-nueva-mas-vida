#!/bin/bash

# Script para desplegar a Google Cloud Run Jobs
set -e

# Configuración
PROJECT_ID=${1:-""}
REGION=${2:-"us-central1"}
SERVICE_NAME="znt-template-pipe-python"

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: Se requiere especificar el PROJECT_ID"
    echo "Uso: $0 <PROJECT_ID> [REGION]"
    echo "Ejemplo: $0 mi-proyecto-gcp us-central1"
    exit 1
fi

echo "🚀 Desplegando $SERVICE_NAME a Google Cloud Run Jobs..."
echo "📍 Proyecto: $PROJECT_ID"
echo "🌍 Región: $REGION"

# Verificar que gcloud está instalado y autenticado
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI no está instalado. Por favor instala Google Cloud SDK."
    exit 1
fi

# Verificar autenticación
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ No estás autenticado con gcloud. Ejecuta: gcloud auth login"
    exit 1
fi

# Configurar proyecto
echo "⚙️ Configurando proyecto..."
gcloud config set project $PROJECT_ID

# Habilitar APIs necesarias
echo "🔌 Habilitando APIs necesarias..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com

# Crear secrets si no existen (ejemplo)
echo "🔐 Verificando secrets..."
if ! gcloud secrets describe database-secrets &> /dev/null; then
    echo "⚠️ Secret 'database-secrets' no existe. Creando ejemplo..."
    echo "host=localhost
port=5432
database=ejemplo
username=usuario
password=password" | gcloud secrets create database-secrets --data-file=-
    echo "📝 Por favor actualiza el secret con valores reales:"
    echo "   gcloud secrets versions add database-secrets --data-file=path/to/real/secrets"
fi

# Construir y desplegar usando Cloud Build
echo "🏗️ Iniciando build y deploy con Cloud Build..."
gcloud builds submit \
    --config cloudbuild.yaml \
    --substitutions _SERVICE_NAME=$SERVICE_NAME,_REGION=$REGION

# Verificar el despliegue
echo "✅ Verificando despliegue..."
gcloud run jobs describe $SERVICE_NAME --region=$REGION

echo ""
echo "🎉 ¡Despliegue completado exitosamente!"
echo ""
echo "Comandos útiles:"
echo "📋 Ver jobs: gcloud run jobs list --region=$REGION"
echo "🚀 Ejecutar job: gcloud run jobs execute $SERVICE_NAME --region=$REGION"
echo "📊 Ver logs: gcloud run jobs executions list --job=$SERVICE_NAME --region=$REGION"
echo "🔍 Ver detalles: gcloud run jobs describe $SERVICE_NAME --region=$REGION"
echo ""
