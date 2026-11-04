param([Parameter(Mandatory=$true)][string]$Folder)
$ErrorActionPreference='Stop'
$folder=(Resolve-Path -LiteralPath $Folder).Path
$targets=Get-Content -LiteralPath (Join-Path $folder 'geometry-targets.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$result=@();$color=[int]0x55aa33
function Find-Layer($shapes,$id){
 foreach($shape in $shapes){
  if($shape.Type -eq 6){$found=Find-Layer $shape.GroupItems $id;if($found){return $found}}
  elseif($shape.AlternativeText -like ('LayerDeck:'+$id+';*')){return $shape}
 }
 return $null
}
foreach($suffix in @('pptx','docx')){
 $out=Join-Path $folder ('native-geometry-edit-check.'+$suffix)
 if(Test-Path -LiteralPath $out){throw ('Prior editing evidence preserved: '+$out)}
}
$ppt=New-Object -ComObject PowerPoint.Application;$initial=$ppt.Presentations.Count
try{
 $deck=$ppt.Presentations.Open((Join-Path $folder 'converted.pptx'),0,0,0)
 try{
  $checks=@()
  foreach($target in $targets){
   $shape=Find-Layer $deck.Slides.Item(1).Shapes $target.id
   if(-not $shape -or $shape.Type -eq 13){throw 'Expected editable native geometry, not a picture'}
   $shape.Fill.Solid();$shape.Fill.ForeColor.RGB=$color;$shape.Fill.Transparency=.25
   $shape.Left=$shape.Left+20;$shape.Top=$shape.Top-10
   $checks+=@{id=$target.id;type=[int]$shape.Type;x=[double]$shape.Left;y=[double]$shape.Top}
  }
  $deck.SaveAs((Join-Path $folder 'native-geometry-edit-check.pptx'))
 }finally{$deck.Close()}
 $saved=$ppt.Presentations.Open((Join-Path $folder 'native-geometry-edit-check.pptx'),-1,0,0)
 try{
  foreach($check in $checks){
   $shape=Find-Layer $saved.Slides.Item(1).Shapes $check.id
   $ok=$shape -and [int]$shape.Fill.ForeColor.RGB -eq $color -and [Math]::Abs($shape.Fill.Transparency-.25) -lt .001 -and [Math]::Abs($shape.Left-$check.x) -lt .01 -and [Math]::Abs($shape.Top-$check.y) -lt .01
   $result+=@{format='pptx';id=$check.id;nativeType=$check.type;reopened=[bool]$ok;changed='fill, opacity, position'}
  }
 }finally{$saved.Close()}
}finally{if($initial -eq 0 -and $ppt.Presentations.Count -eq 0){$ppt.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt)|Out-Null}
$word=New-Object -ComObject Word.Application;$initial=$word.Documents.Count;$alerts=$word.DisplayAlerts
try{
 $word.DisplayAlerts=0
 $doc=$word.Documents.Open((Join-Path $folder 'converted.docx'),$false,$false,$false)
 try{
  $checks=@()
  foreach($target in $targets){
   $shape=$doc.Shapes.Item('layer_'+$target.id)
   if($shape.Type -eq 13){throw 'Expected native Word geometry'}
   $shape.Fill.Solid();$shape.Fill.ForeColor.RGB=$color;$shape.Fill.Transparency=.25
   $shape.Left=$shape.Left+20;$shape.Top=$shape.Top-10
   $checks+=@{id=$target.id;type=[int]$shape.Type;x=[double]$shape.Left;y=[double]$shape.Top}
  }
  [object]$savePath=[string](Join-Path $folder 'native-geometry-edit-check.docx');[object]$saveFormat=[int]12
  $doc.SaveAs([ref]$savePath,[ref]$saveFormat)
 }finally{$doc.Close(0)}
 $saved=$word.Documents.Open((Join-Path $folder 'native-geometry-edit-check.docx'),$false,$true,$false)
 try{
  foreach($check in $checks){
   $shape=$saved.Shapes.Item('layer_'+$check.id)
   $ok=[int]$shape.Fill.ForeColor.RGB -eq $color -and [Math]::Abs($shape.Fill.Transparency-.25) -lt .001 -and [Math]::Abs($shape.Left-$check.x) -lt .01 -and [Math]::Abs($shape.Top-$check.y) -lt .01
   $result+=@{format='docx';id=$check.id;nativeType=$check.type;reopened=[bool]$ok;changed='fill, opacity, position'}
  }
 }finally{$saved.Close(0)}
}finally{$word.DisplayAlerts=$alerts;if($initial -eq 0 -and $word.Documents.Count -eq 0){$word.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)|Out-Null}
$result|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $folder 'geometry-edit-validation.json') -Encoding UTF8
if(@($result|Where-Object {-not $_.reopened}).Count){throw 'Native geometry editing did not persist'}
Write-Output ('Reopened '+$result.Count+' native geometry edits across PowerPoint and Word.')
