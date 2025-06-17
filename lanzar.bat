@echo off
setlocal enabledelayedexpansion
REM añadir a lo bestia.
git add .

REM Pedir número de versión
set /p VERSION=Introduce el número de versión (ej: 1.2.3): 

REM Hacer commit con el mensaje
git commit -am "Release %VERSION%"
if errorlevel 1 (
    echo Error en el commit. Asegúrate de tener cambios preparados.
    goto :eof
)

REM Crear el tag
git tag v%VERSION%
if errorlevel 1 (
    echo Error al crear el tag.
    goto :eof
)

REM Push del commit y del tag
git push
git push origin v%VERSION%

echo ===========================
echo Versión %VERSION% publicada.
echo ===========================

endlocal
pause
