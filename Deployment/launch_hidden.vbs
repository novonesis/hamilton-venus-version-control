Set objShell = CreateObject("WScript.Shell")
' Run the BAT script hidden (0)
' The path to the BAT script is relative to the VBS script's location
' The 'True' parameter waits for the script to finish
objShell.Run "run_app.bat", 0, True
Set objShell = Nothing