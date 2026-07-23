<#
    parse_workitem.ps1

    Parses a large Azure DevOps work item JSON file (the kind the MCP writes
    to disk when the inline response would be too large) into a clean,
    flat object containing fields, HTML-stripped Description / Acceptance
    Criteria, and the list of attachments.

    Usage:
        pwsh -File parse_workitem.ps1 -FilePath "<path to work item json>"

    Output:
        A single JSON object (via ConvertTo-Json) printed to stdout.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath
)

Add-Type -AssemblyName System.Web

$j = Get-Content $FilePath -Raw | ConvertFrom-Json

function Convert-Html {
    param([string]$Html)

    if ([string]::IsNullOrWhiteSpace($Html)) {
        return ""
    }

    $tmp = $Html `
        -replace '<br\s*/?>', "`n" `
        -replace '</(p|div|h1|h2|h3|li)>', "`n" `
        -replace '<li[^>]*>', '- ' `
        -replace '<[^>]+>', ' '

    $tmp = [System.Web.HttpUtility]::HtmlDecode($tmp)
    $tmp = $tmp -replace '&nbsp;', ' '

    ($tmp -split "`n" |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -ne "" }) -join "`n"
}

$result = [PSCustomObject]@{

    Id = $j.fields.'System.Id'
    Title = $j.fields.'System.Title'
    State = $j.fields.'System.State'
    AssignedTo = $j.fields.'System.AssignedTo'.displayName
    AreaPath = $j.fields.'System.AreaPath'
    IterationPath = $j.fields.'System.IterationPath'
    WorkItemType = $j.fields.'System.WorkItemType'
    Description = Convert-Html $j.fields.'System.Description'
    AcceptanceCriteria = Convert-Html $j.fields.'Microsoft.VSTS.Common.AcceptanceCriteria'

    Attachments = @(
        $j.relations |
        Where-Object { $_.rel -eq "AttachedFile" } |
        ForEach-Object {
            [PSCustomObject]@{
                Name   = $_.attributes.name
                SizeKB = [math]::Round($_.attributes.resourceSize / 1024, 1)
                Id     = ($_.url -split '/')[-1]
            }
        }
    )

}

$result | ConvertTo-Json -Depth 5
 