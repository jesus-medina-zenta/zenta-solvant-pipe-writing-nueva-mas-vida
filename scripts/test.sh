#!/bin/bash

# Script para ejecutar tests con diferentes configuraciones
set -e

echo "🧪 Ejecutando suite de tests..."

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Función para ejecutar tests básicos
run_basic_tests() {
    echo "📋 Ejecutando tests básicos..."
    python -m pytest tests/ -v
}

# Función para ejecutar tests con cobertura
run_coverage_tests() {
    echo "📊 Ejecutando tests con cobertura..."
    python -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term
    echo "📈 Reporte de cobertura generado en htmlcov/"
}

# Función para ejecutar solo tests rápidos
run_fast_tests() {
    echo "⚡ Ejecutando tests rápidos..."
    python -m pytest tests/ -v -m "not slow"
}

# Función para ejecutar tests de integración
run_integration_tests() {
    echo "🔗 Ejecutando tests de integración..."
    python -m pytest tests/ -v -m "integration"
}

# Función para verificar calidad de código
run_quality_checks() {
    echo "🔍 Verificando calidad de código..."
    
    echo "🖤 Ejecutando black..."
    black --check src/ tests/
    
    echo "📏 Ejecutando flake8..."
    flake8 src/ tests/
    
    echo "🔎 Ejecutando mypy..."
    mypy src/
}

# Parsear argumentos
case "${1:-all}" in
    "basic")
        run_basic_tests
        ;;
    "coverage")
        run_coverage_tests
        ;;
    "fast")
        run_fast_tests
        ;;
    "integration")
        run_integration_tests
        ;;
    "quality")
        run_quality_checks
        ;;
    "all")
        run_quality_checks
        run_coverage_tests
        ;;
    *)
        echo "Uso: $0 [basic|coverage|fast|integration|quality|all]"
        echo ""
        echo "Opciones:"
        echo "  basic       - Tests básicos sin cobertura"
        echo "  coverage    - Tests con reporte de cobertura"
        echo "  fast        - Solo tests rápidos (excluye tests marcados como 'slow')"
        echo "  integration - Solo tests de integración"
        echo "  quality     - Verificaciones de calidad de código (black, flake8, mypy)"
        echo "  all         - Todas las verificaciones (por defecto)"
        exit 1
        ;;
esac

echo "✅ Tests completados exitosamente!"
