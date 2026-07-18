function ConvertTo-ValidatedScenarioInventory {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][AllowNull()][object]$InputObject)

    $items = @($InputObject)
    if ($items.Count -eq 0 -or ($items.Count -eq 1 -and $null -eq $items[0])) {
        throw "Scenario inventory must contain at least one scenario object."
    }

    foreach ($item in $items) {
        if ($null -eq $item) {
            throw "Scenario inventory contains a null scenario object."
        }
        $domainProperty = $item.PSObject.Properties['domain']
        $idProperty = $item.PSObject.Properties['scenario_id']
        if ($null -eq $domainProperty -or [string]::IsNullOrWhiteSpace([string]$domainProperty.Value)) {
            throw "Every scenario object must contain a non-empty 'domain' property."
        }
        if ($null -eq $idProperty -or [string]::IsNullOrWhiteSpace([string]$idProperty.Value)) {
            throw "Every scenario object must contain a non-empty 'scenario_id' property."
        }
        [PSCustomObject][ordered]@{
            domain = [string]$domainProperty.Value
            scenario_id = [string]$idProperty.Value
        }
    }
}

function Get-ScenarioInventoryDomains {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object[]]$Scenarios)

    @($Scenarios | ForEach-Object {
        if ($null -eq $_ -or $null -eq $_.PSObject.Properties['domain']) {
            throw "Cannot enumerate domains because a scenario object is null or missing 'domain'."
        }
        [string]$_.PSObject.Properties['domain'].Value
    } | Sort-Object -Unique)
}
