Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c ""cd /d C:\EhkoDev\recog-ui && npm run dev""", 0
Set WshShell = Nothing
