# Run build_scene.py in a windowless Blender and wait for it, so that a live Blender session is left alone.
#   .\run_headless.ps1                                  build inhabited_room.blend
#   .\run_headless.ps1 --render arrival,section,plan    build it and render those views into .\views
# A windowless Blender prints nothing back: progress and any error are in build.log, shown when it ends.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here "build.log"
Remove-Item $log -ErrorAction SilentlyContinue
$blender = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\blender-launcher.exe"   # the Microsoft Store Blender: its blender.exe cannot be started directly
$arguments = @("--background", "--factory-startup", "--disable-autoexec", "--python", "`"$(Join-Path $here 'build_scene.py')`"", "--") + @($args | ForEach-Object { "$_" })   # every argument as text: a bare number is not one
Start-Process $blender -ArgumentList $arguments -WindowStyle Hidden
$waited = 0
while ($waited -lt 1500) {
    Start-Sleep -Seconds 3
    $waited += 3
    if ((Test-Path $log) -and ((Get-Content $log -Raw) -match "(?m)^\d\d:\d\d:\d\d (done|FAILED|pose sheet rendered)")) { break }
}
Get-Content $log
