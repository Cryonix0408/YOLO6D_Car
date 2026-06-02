$env:YOLO_CONFIG_DIR = "D:\Envs\ultralytics_config"
$env:PIP_CACHE_DIR = "G:\AI_Cache\pip"

# Run from PowerShell with:
# . .\scripts\activate_yolo6d_env.ps1
(& "G:\Software\Miniforge3\Scripts\conda.exe" "shell.powershell" "hook") | Out-String | Invoke-Expression
conda activate "D:\Envs\yolo6d"
