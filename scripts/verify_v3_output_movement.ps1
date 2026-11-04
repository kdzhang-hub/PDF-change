param([Parameter(Mandatory=$true)][string]$Folder)
$ErrorActionPreference='Stop'
$folder=(Resolve-Path -LiteralPath $Folder).Path
$targets=Get-Content -LiteralPath (Join-Path $folder 'movement-targets.json') -Raw -Encoding UTF8|ConvertFrom-Json
function Find-Layer($shapes,$id){
 foreach($shape in $shapes){
  if($shape.Type -eq 6){$found=Find-Layer $shape.GroupItems $id;if($found){return $found}}
  elseif($shape.AlternativeText -like ('LayerDeck:'+$id+';*')){return $shape}
 }
 return $null
}
$app=New-Object -ComObject PowerPoint.Application;$initial=$app.Presentations.Count;$checks=@()
try{
 foreach($target in $targets){
  $deck=$app.Presentations.Open((Join-Path $folder 'converted.pptx'),0,0,0)
  try{
   $slide=$deck.Slides.Item([int]$target.slide);$shape=Find-Layer $slide.Shapes $target.id
   if(-not $shape){throw ('Exported object identity missing: '+$target.id)}
   $before=@([double]$shape.Left,[double]$shape.Top)
   $shape.Visible=0;$slide.Export((Join-Path $folder ('hidden-'+$target.role+'.png')),'PNG',1200,675);$shape.Visible=-1
   $shape.Left=$shape.Left+[double]$target.dx;$shape.Top=$shape.Top+[double]$target.dy
   $after=@([double]$shape.Left,[double]$shape.Top)
   $path=Join-Path $folder ('moved-'+$target.role+'.pptx');$deck.SaveAs($path)
   $slide.Export((Join-Path $folder ('moved-'+$target.role+'.png')),'PNG',1200,675)
  }finally{$deck.Close()}
  $saved=$app.Presentations.Open($path,-1,0,0)
  try{
   $shape=Find-Layer $saved.Slides.Item([int]$target.slide).Shapes $target.id
   $ok=$null -ne $shape -and [Math]::Abs($shape.Left-$after[0]) -lt .01 -and [Math]::Abs($shape.Top-$after[1]) -lt .01
  }finally{$saved.Close()}
  $checks+=@{role=$target.role;slide=$target.slide;layer=$target.id;before=$before;after=$after;reopened=$ok;source=$target.source;semantic=$target.semantic}
 }
}finally{if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
$checks|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $folder 'movement-validation.json') -Encoding UTF8
if(@($checks|Where-Object {-not $_.reopened}).Count){throw 'Movement persistence check failed'}
Write-Output ('Moved and reopened '+$checks.Count+' independent output objects; hidden and moved screenshots retained.')
