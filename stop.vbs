Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr "":8000\>"" 2^>nul') do taskkill /f /t /pid %a >nul 2>&1", 0, True
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr "":3000\>"" 2^>nul') do taskkill /f /t /pid %a >nul 2>&1", 0, True
