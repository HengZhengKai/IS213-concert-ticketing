# Try to find the IPv4 address of the network interface with a default gateway
$hostIP = Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred | `
    Where-Object { $_.IPAddress -ne '127.0.0.1' -and !$_.IPAddress.StartsWith('169.254.') } | `
    Where-Object { (Get-NetIPConfiguration -InterfaceIndex $_.InterfaceIndex).IPv4DefaultGateway -ne $null } | `
    Select-Object -First 1 -ExpandProperty IPAddress

# Fallback if the above didn't find anything (e.g., unusual network setup)
if (-not $hostIP) {
    Write-Warning "Could not reliably determine IP via default gateway. Falling back to previous method."
    $hostIP = Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred | `
        Where-Object { $_.IPAddress -ne '127.0.0.1' -and !$_.IPAddress.StartsWith('169.254.') } | `
        Select-Object -First 1 -ExpandProperty IPAddress
}

if (-not $hostIP) {
    Write-Error "Could not automatically detect a suitable host IP address."
    # Optionally, prompt the user
    # $hostIP = Read-Host "Please enter the host IP address for your Wi-Fi/LAN connection"
    exit 1
}

Write-Host "Using Host IP: $hostIP (This should be your Wi-Fi/LAN IP)"

# Set the environment variable for Docker Compose
$env:HOST_IP = $hostIP

Write-Host "Starting Docker containers with HOST_IP=$hostIP... (including build)"

# Run Docker Compose, forcing a rebuild of images if necessary
docker-compose up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host "Docker containers started successfully."
} else {
    Write-Error "Docker Compose failed to start containers. Exit code: $LASTEXITCODE"
}

# Optional: Keep the window open for a few seconds
# Start-Sleep -Seconds 5 