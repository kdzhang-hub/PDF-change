$ErrorActionPreference='Stop'
$folder=Join-Path (Split-Path -Parent $PSScriptRoot) 'work\font-resolution'
$app=New-Object -ComObject PowerPoint.Application
$initial=$app.Presentations.Count
try{
 $deck=$app.Presentations.Open((Join-Path $folder 'probe.pptx'),-1,0,0)
 try{$deck.SaveCopyAs((Join-Path $folder 'probe.pdf'),32)}finally{$deck.Close()}
}finally{if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
