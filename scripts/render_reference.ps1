$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$out=Join-Path $root 'deliverables\real-case-20261027\reference-powerpoint.pdf'
$source=Join-Path $root 'deliverables\real-case-20261027\reference-input.pptx'
$office=New-Object -ComObject PowerPoint.Application
$initial=$office.Presentations.Count
try {
    $deck=$office.Presentations.Open($source,-1,0,0)
    try {$deck.SaveCopyAs($out,32)}finally{$deck.Close()}
} finally {
    if($initial -eq 0 -and $office.Presentations.Count -eq 0){$office.Quit()}
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($office)|Out-Null
}
Write-Output 'Reference PPT rendered read-only.'
