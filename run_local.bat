@echo off
REM ===========================================================================
REM  ar-acc - Script de arranque local para Windows (Zero-Docker)
REM  1) Crea/verifica el entorno virtual   2) Instala dependencias
REM  3) Puebla Neo4j con el dataset demo   4) Levanta el dashboard Streamlit
REM ===========================================================================

setlocal
cd /d "%~dp0"

echo.
echo ========================================
echo   ar-acc - Arranque local
echo ========================================
echo.

REM --- 1. Entorno virtual ---------------------------------------------------
if not exist "venv\Scripts\activate.bat" (
    echo [1/4] Creando entorno virtual "venv"...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: no se pudo crear el entorno virtual.
        echo Verifica que Python 3.10+ este instalado y en el PATH.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Entorno virtual "venv" ya existe.
)

call "venv\Scripts\activate.bat"

REM --- 2. Dependencias ------------------------------------------------------
echo [2/4] Instalando dependencias desde requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: fallo la instalacion de dependencias.
    pause
    exit /b 1
)

REM --- 3. Ingesta a Neo4j ---------------------------------------------------
echo [3/4] Poblando Neo4j con el dataset de prueba...
python -m pipelines.import_to_neo4j
if errorlevel 1 (
    echo ERROR: fallo la ingesta a Neo4j.
    echo Revisa el archivo .env y que la base de datos este activa.
    pause
    exit /b 1
)

REM --- 4. Dashboard Streamlit ----------------------------------------------
echo [4/4] Iniciando el dashboard Streamlit...
echo.
streamlit run web\app_streamlit.py

endlocal
