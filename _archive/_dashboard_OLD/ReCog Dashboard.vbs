Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c ""cd /d G:\Other computers\Ehko\Obsidian\ReCog\_dashboard && npm run dev""", 0
Set WshShell = Nothing
