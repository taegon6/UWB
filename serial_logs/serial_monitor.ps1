param(
  [string]$Port = "COM5",
  [int]$Baud = 115200,
  [string]$OutFile = "C:\Users\User\Desktop\3-1\uwb\serial_logs\com5_live.log"
)
$ErrorActionPreference = "Stop"
"=== SERIAL MONITOR START port=$Port baud=$Baud time=$(Get-Date -Format o) ===" | Out-File -FilePath $OutFile -Append -Encoding utf8
$sp = New-Object System.IO.Ports.SerialPort $Port,$Baud,None,8,one
$sp.ReadTimeout = 500
$sp.DtrEnable = $false
$sp.RtsEnable = $true
try {
  $sp.Open()
  Start-Sleep -Milliseconds 1200
  while ($true) {
    try {
      $line = $sp.ReadLine()
      if ($line -ne $null) {
        $stamp = Get-Date -Format "HH:mm:ss.fff"
        "[$stamp] $($line.Trim())" | Out-File -FilePath $OutFile -Append -Encoding utf8
      }
    } catch [System.TimeoutException] {}
  }
} finally {
  if ($sp.IsOpen) { $sp.Close() }
  "=== SERIAL MONITOR STOP time=$(Get-Date -Format o) ===" | Out-File -FilePath $OutFile -Append -Encoding utf8
}
