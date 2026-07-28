@echo off
REM Script para exportar rápidamente a PNG usando herramientas de Windows
REM Simplemente abre el navegador para que captures la pantalla

echo.
echo =========================================
echo   EXPORTADOR RAPIDO DE MAPA A PNG
echo =========================================
echo.
echo Abriendo el mapa en el navegador...
echo.

REM Abrir el archivo HTML
start /max mapa_zonas.html

timeout /t 2

echo.
echo ✓ El mapa está abierto
echo.
echo INSTRUCCIONES RAPIDAS:
echo =======================
echo.
echo OPCION 1 (MAS RAPIDO):
echo   1. Presiona: Windows + Shift + S
echo   2. Dibuja alrededor del mapa
echo   3. Se guarda automáticamente
echo.
echo OPCION 2:
echo   1. Presiona: Ctrl + P
echo   2. Elige "Guardar como PDF"
echo.
echo OPCION 3:
echo   1. Descarga e instala "Fireshot" para Chrome/Firefox
echo   2. Haz clic derecho en el mapa
echo   3. "Captura con Fireshot" > Guardar como PNG
echo.

