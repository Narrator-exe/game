@echo off
setlocal

if "%OLLAMA_MODEL%"=="" set OLLAMA_MODEL=tinyllama:1.1b
if "%SIM_TICK_SECONDS%"=="" set SIM_TICK_SECONDS=8
if "%MAX_MEMORIES%"=="" set MAX_MEMORIES=48

echo Starting lightweight NPC stack for Windows laptops...
echo Model=%OLLAMA_MODEL% TickSeconds=%SIM_TICK_SECONDS% MaxMemories=%MAX_MEMORIES%

docker compose up --build
