# PCSX2 Multi-Instance Launcher
$paths = @(
    "C:\Users\jerem\Documents\PCSX2\pcsx2-qt.exe",
    "C:\Users\jerem\Documents\PCSX2_2\pcsx2-qt2.exe",
    "C:\Users\jerem\Documents\PCSX2_3\pcsx2-qt3.exe",
    "C:\Users\jerem\Documents\PCSX2_4\pcsx2-qt4.exe"
)

foreach ($exe in $paths) {
    Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe)
}
