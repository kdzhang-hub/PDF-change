param([string]$Folder)
$ErrorActionPreference='Stop'
$app=New-Object -ComObject PowerPoint.Application
$initial=$app.Presentations.Count
try{
 $deck=$app.Presentations.Open((Join-Path $Folder 'probe.pptx'),-1,0,0)
 try{
  for($i=1;$i -le $deck.Slides.Count;$i++){
   $deck.Slides.Item($i).Export((Join-Path $Folder ('probe-'+$i+'.png')),'PNG',3200,1800)
  }
 }finally{$deck.Close()}
}finally{if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
