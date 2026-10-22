param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Name
)

$ErrorActionPreference = 'Stop'

try {
    $allUsers = $false
    $vpnProfile = Get-VpnConnection -Name $Name -ErrorAction SilentlyContinue
    if (-not $vpnProfile) {
        $allUsers = $true
        $vpnProfile = Get-VpnConnection -Name $Name -AllUserConnection
    }
    if ($vpnProfile.ConnectionStatus -eq 'Disconnected') {
        Write-Output 'VPN is already disconnected.'
        exit 0
    }

    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Threading;

public static class WindowsVpnDisconnect
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode, Pack = 4)]
    private struct Connection
    {
        public uint Size;
        public IntPtr Handle;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 257)] public string EntryName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 17)] public string DeviceType;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 129)] public string DeviceName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string Phonebook;
        public uint SubEntry;
        public Guid EntryId;
        public uint Flags;
        public ulong LogonId;
        public Guid CorrelationId;
    }

    [DllImport("rasapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint RasEnumConnectionsW(
        [In, Out] Connection[] connections, ref uint bytes, out uint count);

    [DllImport("rasapi32.dll", ExactSpelling = true)]
    private static extern uint RasHangUpW(IntPtr connection);

    public static void Disconnect(Guid entryId)
    {
        int size = Marshal.SizeOf(typeof(Connection));
        Connection[] connections = new Connection[1];
        uint count, error;
        do
        {
            connections[0].Size = (uint)size;
            uint bytes = (uint)(connections.Length * size);
            error = RasEnumConnectionsW(connections, ref bytes, out count);
            if (error == 603) // ERROR_BUFFER_TOO_SMALL: another VPN may also be active.
                connections = new Connection[(bytes + (uint)size - 1) / (uint)size];
        } while (error == 603);
        if (error != 0)
            throw new InvalidOperationException("RasEnumConnections failed: " + error);

        bool requested = false;
        try
        {
            for (uint i = 0; i < count; i++)
            {
                // Match the selected profile's GUID to leave other VPNs connected.
                if (connections[i].EntryId != entryId)
                    continue;
                error = RasHangUpW(connections[i].Handle);
                if (error != 0 && error != 6) // ERROR_INVALID_HANDLE: already gone.
                    throw new InvalidOperationException("RasHangUp failed: " + error);
                requested = true;
            }
        }
        finally
        {
            // Windows requires time for port cleanup before the calling process exits.
            // https://learn.microsoft.com/windows/win32/api/ras/nf-ras-rashangupw
            if (requested)
                Thread.Sleep(3000);
        }
    }
}
'@

    Write-Output 'Disconnecting Windows VPN...'
    [WindowsVpnDisconnect]::Disconnect([Guid]$vpnProfile.Guid)
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        $vpnProfile = Get-VpnConnection -Name $Name -AllUserConnection:$allUsers
        if ($vpnProfile.ConnectionStatus -eq 'Disconnected') {
            Write-Output 'VPN disconnected.'
            exit 0
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Timed out waiting for Windows to disconnect the VPN.'
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
