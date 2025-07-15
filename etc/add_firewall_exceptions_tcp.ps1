# Run this as Administrator

$ports = @(18000, 18001)

foreach ($port in $ports) {
    # Inbound rules
    New-NetFirewallRule -DisplayName "MysticNights_TCP_$port_IN" -Direction Inbound -Protocol TCP -LocalPort $port -Action Allow

    # Outbound rules (for server replies and client activity)
    New-NetFirewallRule -DisplayName "MysticNights_TCP_$port_OUT" -Direction Outbound -Protocol TCP -LocalPort $port -Action Allow
}
