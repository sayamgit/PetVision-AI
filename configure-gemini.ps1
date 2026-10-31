param([switch]$FromClipboard)
$ErrorActionPreference = 'Stop'
Write-Host 'Use a project marked Free Tier in https://aistudio.google.com/api-keys'
Write-Host 'Keep billing disabled. PetVision cannot verify billing from an API key.'
$confirmation = Read-Host 'Does the key belong to a Free Tier project with billing disabled? Type FREE to continue'
if ($confirmation -cne 'FREE') { Write-Host 'No changes made.'; exit 1 }
$secret = $null
$pointer = [IntPtr]::Zero
try {
    if ($FromClipboard) {
        $null = Read-Host 'Now copy the full key from AI Studio. Return here and press Enter WITHOUT pasting it'
        $value = Get-Clipboard -Raw
    } else {
        $secret = Read-Host 'Paste your Gemini API key (hidden)' -AsSecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
        $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    if ([string]::IsNullOrWhiteSpace($value)) { throw 'No text received. No file was written.' }
    $value = $value.Trim()
    # Accept printable header-safe tokens instead of assuming a provider key format.
    # Google will validate the credential. Never display the value, even on failure.
    if ($value.Length -lt 20 -or $value.Length -gt 4096) {
        throw ('Received ' + $value.Length + ' characters; expected a full key. No file was written.')
    }
    if ($value -match '[^\x21-\x7E]') {
        throw 'The copied text contains whitespace or non-ASCII characters. Use Copy key in AI Studio. No file was written.'
    }
    if ($value.StartsWith('http') -or $value.Contains('...') -or $value.Contains([char]34) -or $value.Contains([char]39)) {
        throw 'Received a link, shortened key, or quoted text. Copy only the full key from AI Studio. No file was written.'
    }
    $path = Join-Path $PSScriptRoot '.env.gemini'
    if (Test-Path -LiteralPath $path) {
        $replace = Read-Host 'A saved key exists. Type REPLACE to overwrite it'
        if ($replace -cne 'REPLACE') { Write-Host 'No changes made.'; exit 1 }
    }
    [IO.File]::WriteAllText($path, "GEMINI_API_KEY=$value`nPETVISION_FREE_TIER_CONFIRMED=1`n", [Text.UTF8Encoding]::new($false))
    # Restrict the credential file to this Windows user and SYSTEM.
    $acl = Get-Acl -LiteralPath $path
    $acl.SetAccessRuleProtection($true, $false)
    $owner = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($owner,'FullControl','Allow'))
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-18'),'FullControl','Allow'))
    Set-Acl -LiteralPath $path -AclObject $acl
    Write-Host 'Key saved privately. Refresh Pet chat; the server reads it automatically. Do not share .env.gemini.'
} finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    $value = $null
    if ($null -ne $secret) { $secret.Dispose() }
}
