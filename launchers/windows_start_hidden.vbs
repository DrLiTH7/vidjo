Set objShell = CreateObject("WScript.Shell")
' Executa o .bat de forma oculta (sem janela de terminal visível)
objShell.Run chr(34) & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\windows_start.bat" & chr(34), 0, False
