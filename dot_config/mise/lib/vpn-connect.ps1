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
    if ($vpnProfile.ConnectionStatus -eq 'Connected') {
        Write-Output 'VPN is already connected.'
        exit 0
    }

    $basePath = if ($allUsers) { $env:ProgramData } else { $env:APPDATA }
    $phonebook = Join-Path $basePath 'Microsoft\Network\Connections\Pbk\rasphone.pbk'

    # Windows RAS uses 4-byte packing, including on 64-bit Windows.
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class WindowsVpn
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode, Pack = 4)]
    private struct Credentials
    {
        public uint Size;
        public uint Mask;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 257)] public string UserName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 257)] public string Password;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 16)] public string Domain;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode, Pack = 4)]
    private struct DialParameters
    {
        public uint Size;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 257)] public string EntryName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 129)] public string PhoneNumber;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 129)] public string CallbackNumber;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 257)] public string UserName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 257)] public string Password;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 16)] public string Domain;
        public uint SubEntry;
        public UIntPtr CallbackId;
        public uint InterfaceIndex;
        public IntPtr EncryptedPassword;
    }

    [DllImport("rasapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint RasGetCredentialsW(
        string phonebook, string entry, ref Credentials credentials);

    [DllImport("rasapi32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern uint RasDialW(
        IntPtr extensions, string phonebook, ref DialParameters parameters,
        uint notifierType, IntPtr notifier, out IntPtr connection);

    [DllImport("rasapi32.dll", ExactSpelling = true)]
    private static extern uint RasHangUpW(IntPtr connection);

    public static void Connect(string phonebook, string entry)
    {
        const uint UserName = 1, Password = 2, Domain = 4;
        Credentials credentials = new Credentials();
        credentials.Size = (uint)Marshal.SizeOf(typeof(Credentials));
        credentials.Mask = UserName | Password | Domain;
        uint error = RasGetCredentialsW(phonebook, entry, ref credentials);
        if (error != 0)
            throw new InvalidOperationException("RasGetCredentials failed: " + error);
        if ((credentials.Mask & (UserName | Password)) != (UserName | Password)
            || String.IsNullOrEmpty(credentials.UserName))
            throw new InvalidOperationException(
                "Save the VPN user name and password in Windows VPN settings first.");

        DialParameters parameters = new DialParameters();
        parameters.Size = (uint)Marshal.SizeOf(typeof(DialParameters));
        parameters.EntryName = entry;
        parameters.UserName = credentials.UserName;
        // RasGetCredentials returns a saved-password handle, not the password.
        // https://learn.microsoft.com/windows/win32/api/ras/nf-ras-rasgetcredentialsw
        parameters.Password = credentials.Password;
        parameters.Domain = (credentials.Mask & Domain) != 0 ? credentials.Domain : "";
        IntPtr connection;
        // A null notifier makes RasDial wait for connection success or failure.
        error = RasDialW(IntPtr.Zero, phonebook, ref parameters, 0, IntPtr.Zero, out connection);
        if (error != 0)
        {
            if (connection != IntPtr.Zero)
                RasHangUpW(connection);
            throw new InvalidOperationException("RasDial failed: " + error);
        }
        // Keep a successful connection alive for the user's Windows session.
    }
}
'@

    Write-Output 'Connecting Windows VPN using saved credentials...'
    [WindowsVpn]::Connect($phonebook, $Name)
    $vpnProfile = Get-VpnConnection -Name $Name -AllUserConnection:$allUsers
    if ($vpnProfile.ConnectionStatus -ne 'Connected') {
        throw 'Windows did not report the VPN as connected.'
    }
    Write-Output 'VPN connected.'
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
