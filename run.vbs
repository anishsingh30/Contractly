Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 1. Silently clear any old hung processes on ports 8000 and 3000
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr "":8000\>"" 2^>nul') do taskkill /f /t /pid %a >nul 2>&1", 0, True
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr "":3000\>"" 2^>nul') do taskkill /f /t /pid %a >nul 2>&1", 0, True

' 2. Start FastAPI Backend silently with auto-reload (no window)
WshShell.Run "cmd /c cd /d """ & strDir & """ && backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload", 0, False

' 3. Start Next.js Frontend silently with live hot-reload (no window)
WshShell.Run "cmd /c cd /d """ & strDir & """ && npm.cmd run dev", 0, False

' 4. Wait a few moments for initialization
WScript.Sleep 4000

' 5. Open webpage directly in default browser
WshShell.Run "http://localhost:3000"
