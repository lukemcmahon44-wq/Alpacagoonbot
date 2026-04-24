' Launch jarvis.py silently with pythonw (no console window).
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = scriptDir
sh.Run "pythonw.exe """ & scriptDir & "\jarvis.py""", 0, False
