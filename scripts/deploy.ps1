# Deploy termite_bringup + docker scripts to Jetson, then build the package.
# Usage (repo root): powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1
param([switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
$Jetson = 'chl@192.168.0.108'
$Repo = Split-Path -Parent $PSScriptRoot

Write-Host '[1/4] sync termite_bringup source'
scp -r -o BatchMode=yes "$Repo\ros2_ws\src\termite_bringup" "${Jetson}:~/ros2_ws/src/"

Write-Host '[2/4] sync docker / scripts / offline wheel'
ssh -o BatchMode=yes $Jetson 'mkdir -p ~/termite-rover/docker ~/termite-rover/scripts ~/ros2_ws/vendor'

$dockerFiles = Get-ChildItem "$Repo\docker" -File | Where-Object { $_.Name -in @('entrypoint.sh', 'fixes.sh', 'compose.yaml', 'Dockerfile') }
scp -o BatchMode=yes $dockerFiles.FullName "${Jetson}:~/termite-rover/docker/"

$scriptFiles = Get-ChildItem "$Repo\scripts" -File | Where-Object { $_.Extension -in @('.sh', '.service', '.timer') }
scp -o BatchMode=yes $scriptFiles.FullName "${Jetson}:~/termite-rover/scripts/"

$wheels = Get-ChildItem "$Repo\.cache" -Filter '*.whl' -File -ErrorAction SilentlyContinue
if ($wheels) {
    scp -o BatchMode=yes $wheels.FullName "${Jetson}:~/ros2_ws/vendor/"
} else {
    Write-Host '  (no wheel in .cache, skip offline packages)'
}

ssh -o BatchMode=yes $Jetson 'sed -i "s/\r$//" ~/termite-rover/docker/*.sh ~/termite-rover/scripts/*.sh; chmod +x ~/termite-rover/docker/*.sh ~/termite-rover/scripts/*.sh'

if (-not $SkipBuild) {
    Write-Host '[3/4] colcon build termite_bringup'
    $buildCmd = "docker exec termite_ros2 bash -lc 'source /opt/ros/humble/install/setup.bash && source /root/ros2_ws/install/setup.bash && cd /root/ros2_ws && colcon build --packages-select termite_bringup --symlink-install'"
    ssh -o BatchMode=yes $Jetson $buildCmd
} else {
    Write-Host '[3/4] build skipped'
}

Write-Host '[4/4] done'
