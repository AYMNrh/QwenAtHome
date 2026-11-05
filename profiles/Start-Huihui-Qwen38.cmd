@echo off
if not defined LLAMA_SERVER (
  echo Set LLAMA_SERVER to the full path of llama-server.exe.
  exit /b 1
)
if not defined MODEL_DIR (
  echo Set MODEL_DIR to your model directory.
  exit /b 1
)
"%LLAMA_SERVER%" -m "%MODEL_DIR%\Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf" --alias Huihui-Qwen3.8-27B --host 127.0.0.1 --port 8081 --ctx-size 32768 --parallel 1 --gpu-layers all --fit on --fit-target 512 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --batch-size 512 --ubatch-size 128 --threads 8 --jinja --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0 --repeat-penalty 1.0 --backend-sampling --spec-type draft-mtp --spec-draft-n-max 3 --spec-draft-type-k q8_0 --spec-draft-type-v q8_0
pause
