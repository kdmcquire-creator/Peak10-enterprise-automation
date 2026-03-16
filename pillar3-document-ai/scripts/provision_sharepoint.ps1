<#
.SYNOPSIS
    Provisions the Peak 10 Energy governed document hierarchy in SharePoint.

.DESCRIPTION
    Creates the four top-level document libraries (01_CORPORATE, 02_OPERATIONS,
    03_DEALS, 04_GOVERNANCE) plus the 00_STAGING intake queue, with all
    sub-folders as defined in the architecture.

    Requires: PnP.PowerShell module
    Install:  Install-Module PnP.PowerShell -Scope CurrentUser

.PARAMETER SiteUrl
    The SharePoint site URL (e.g., https://peak10energy.sharepoint.com/sites/Operations)

.PARAMETER LibraryName
    The document library name to provision into (default: "Documents")

.EXAMPLE
    .\provision_sharepoint.ps1 -SiteUrl "https://peak10energy.sharepoint.com/sites/Operations"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$SiteUrl,

    [Parameter(Mandatory = $false)]
    [string]$LibraryName = "Documents"
)

# --- Folder hierarchy definition ---
$FolderHierarchy = @{
    "00_STAGING" = @(
        "Inbox",
        "Processing",
        "Errors"
    )
    "01_CORPORATE" = @(
        "Legal",
        "Legal/Contracts",
        "Legal/Amendments",
        "Legal/NDAs",
        "Finance",
        "Finance/AP",
        "Finance/AR",
        "Finance/Tax",
        "Finance/Audit",
        "Insurance",
        "HR",
        "HR/Policies",
        "HR/Benefits"
    )
    "02_OPERATIONS" = @(
        "Field_Reports",
        "Field_Reports/Daily",
        "Field_Reports/Weekly",
        "Well_Files",
        "AFEs",
        "Production",
        "Production/Decline_Curves",
        "Production/Run_Tickets",
        "Regulatory",
        "Regulatory/RRC",
        "Regulatory/EPA",
        "Vendor_Contracts",
        "Safety",
        "Safety/JSAs",
        "Safety/Incidents"
    )
    "03_DEALS" = @(
        "Active",
        "Active/LOIs",
        "Active/PSAs",
        "Active/Due_Diligence",
        "Active/Title",
        "Closed",
        "Passed",
        "Pipeline"
    )
    "04_GOVERNANCE" = @(
        "Board_Minutes",
        "Operating_Agreements",
        "Bylaws",
        "Resolutions",
        "Compliance",
        "Audit_Reports"
    )
}

# --- Connect to SharePoint ---
Write-Host "Connecting to SharePoint site: $SiteUrl" -ForegroundColor Cyan
Connect-PnPOnline -Url $SiteUrl -Interactive

# --- Create folders ---
$totalCreated = 0

foreach ($topLevel in $FolderHierarchy.Keys | Sort-Object) {
    $topPath = "$LibraryName/$topLevel"
    Write-Host "`nCreating: $topPath" -ForegroundColor Yellow

    try {
        $null = Resolve-PnPFolder -SiteRelativePath $topPath
        $totalCreated++
    }
    catch {
        Write-Host "  ERROR creating $topPath : $_" -ForegroundColor Red
        continue
    }

    foreach ($subFolder in $FolderHierarchy[$topLevel]) {
        $subPath = "$LibraryName/$topLevel/$subFolder"
        Write-Host "  Creating: $subPath" -ForegroundColor Gray

        try {
            $null = Resolve-PnPFolder -SiteRelativePath $subPath
            $totalCreated++
        }
        catch {
            Write-Host "  ERROR creating $subPath : $_" -ForegroundColor Red
        }
    }
}

Write-Host "`nProvisioning complete. $totalCreated folders created/verified." -ForegroundColor Green

# --- Disconnect ---
Disconnect-PnPOnline
