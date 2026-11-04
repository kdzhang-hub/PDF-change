param([string]$Round='00',[string]$Folder='')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if(-not $Folder){$folder=Join-Path $root ('deliverables\real-case-20261027\round-'+$Round)}else{$folder=(Resolve-Path -LiteralPath $Folder).Path}
$office=New-Object -ComObject PowerPoint.Application
$initial=$office.Presentations.Count
try {
    $deck=$office.Presentations.Open((Join-Path $folder 'converted.pptx'),-1,0,0)
    try {
        $deck.SaveCopyAs((Join-Path $folder 'powerpoint.pdf'),32)
        $summary=@()
        for ($i=1;$i -le $deck.Slides.Count;$i++) {
            $slide=$deck.Slides.Item($i)
            $pixelWidth=[int][Math]::Round($deck.PageSetup.SlideWidth*1.25)
            $pixelHeight=[int][Math]::Round($deck.PageSetup.SlideHeight*1.25)
            $slide.Export((Join-Path $folder ('office-'+$i+'.png')),'PNG',$pixelWidth,$pixelHeight)
            $summary+=@{slide=$i;shapes=$slide.Shapes.Count}
        }
        $summary|ConvertTo-Json -Depth 5|Set-Content (Join-Path $folder 'powerpoint-open.json') -Encoding utf8
    } finally { $deck.Close() }
} finally {
    if ($initial -eq 0 -and $office.Presentations.Count -eq 0) {$office.Quit()}
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($office)|Out-Null
}
Write-Output 'PowerPoint opened and rendered the reconstructed deck.'
