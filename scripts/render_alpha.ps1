$ErrorActionPreference='Stop'
$folder=Join-Path (Split-Path -Parent $PSScriptRoot) 'work\alpha-diagnostic'
$app=New-Object -ComObject PowerPoint.Application
$initial=$app.Presentations.Count
try{
 $deck=$app.Presentations.Open((Join-Path $folder 'alpha.pptx'),-1,0,0)
 try{$deck.Slides.Item(1).Export((Join-Path $folder 'office.png'),'PNG',400,200)}finally{$deck.Close()}
}finally{if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
