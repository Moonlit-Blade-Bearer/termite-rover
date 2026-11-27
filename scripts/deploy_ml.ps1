# Deploy termite ML model (model.py + best_multitask.pth) to the Jetson.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\deploy_ml.ps1
param([string]$DataRoot = "E:\白蚁\白蚁数据集")

$ErrorActionPreference = 'Stop'
$Jetson = 'chl@192.168.0.108'

Write-Host '[1/4] check local files'
$files = @(
    (Join-Path $DataRoot 'config.py'),
    (Join-Path $DataRoot 'model.py'),
    (Join-Path $DataRoot 'pipeline.py'),
    (Join-Path $DataRoot 'checkpoints\best_multitask.pth')
)
foreach ($f in $files) {
    if (-not (Test-Path $f)) { throw "missing: $f" }
    Write-Host "  ok $f"
}

Write-Host '[2/4] create remote dir'
ssh -o BatchMode=yes $Jetson 'mkdir -p ~/ros2_ws/ml'

Write-Host '[3/4] copy model files'
scp -o BatchMode=yes $files "${Jetson}:~/ros2_ws/ml/"

Write-Host '[4/4] rebuild + restart'
ssh -o BatchMode=yes $Jetson "docker exec termite_ros2 bash -lc 'source /opt/ros/humble/install/setup.bash; source /root/ros2_ws/install/setup.bash; cd /root/ros2_ws; colcon build --packages-select termite_bringup --symlink-install'"
ssh -o BatchMode=yes $Jetson 'docker restart termite_ros2 >/dev/null 2>&1'
Write-Host 'done. check: docker logs --tail 80 termite_ros2 | grep termite_detector'
