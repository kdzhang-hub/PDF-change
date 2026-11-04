$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$folder=Join-Path $root 'deliverables\real-case-20261027\round-04'
$app=New-Object -ComObject PowerPoint.Application
$initial=$app.Presentations.Count
try {
 $deck=$app.Presentations.Open((Join-Path $folder 'converted.pptx'),-1,0,0)
 try {$range=$deck.PrintOptions.Ranges.Add(1,$deck.Slides.Count);$deck.ExportAsFixedFormat((Join-Path $folder 'print-quality.pdf'),2,2,0,1,1,0,$range,1,'',$false,$true,$true,$true,$false)}finally{$deck.Close()}
}finally{if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
