<#
    extract_docx_text.ps1

    Extracts the raw text content from a .docx file's word/document.xml
    part, stripping XML tags. Used to read .docx attachments on a work
    item without needing Word installed.

    Usage:
        pwsh -File extract_docx_text.ps1 -FilePath "<path to .docx>"

    Output:
        Plain text extracted from the document, printed to stdout.
        If extraction fails, prints: "No se pudo extraer texto del archivo Word."
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath
)

try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($FilePath)

    $entry = $zip.Entries | Where-Object { $_.FullName -eq "word/document.xml" }
    $r = New-Object System.IO.StreamReader($entry.Open())
    $xml = $r.ReadToEnd()

    $r.Close()
    $zip.Dispose()

    $xml -replace '<[^>]+>', ' ' -replace '\s{2,}', ' '
}
catch {"No se pudo extraer texto del archivo Word."}
 