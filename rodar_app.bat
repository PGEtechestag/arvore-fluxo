@echo off
cd /d "%~dp0"
echo ============================================
echo  Arvore de Fluxo Processual - App Streamlit
echo ============================================
echo.
echo Abrindo em: http://localhost:8501
echo (para PARAR o app: feche esta janela ou Ctrl+C)
echo.
set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=py"
rem aceita os dois layouts: com a pasta "visualizacoes" ou tudo na raiz
set "APP=%~dp0visualizacoes\app_streamlit.py"
if not exist "%APP%" set "APP=%~dp0app_streamlit.py"
"%PY%" -m streamlit run "%APP%"
pause
