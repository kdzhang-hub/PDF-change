param([Parameter(Mandatory=$true)][string]$Folder)
$ErrorActionPreference='Stop';$folder=(Resolve-Path -LiteralPath $Folder).Path
$scene=(Get-Content -LiteralPath (Join-Path $folder 'scenes.json') -Raw -Encoding UTF8|ConvertFrom-Json)[0]
$target=$scene.layers|Where-Object {$_.kind -eq 'text' -and $_.visible -and $_.opacity -gt 0}|Select-Object -First 1
if(-not $target){throw 'No visible native text target'}
foreach($name in @('moved-text.pptx','moved-text.docx')){if(Test-Path -LiteralPath (Join-Path $folder $name)){throw 'Existing movement evidence preserved'}}
$checks=@();$ppt=New-Object -ComObject PowerPoint.Application;$initial=$ppt.Presentations.Count
try{
 $deck=$ppt.Presentations.Open((Join-Path $folder 'converted.pptx'),0,0,0)
 try{
  $shape=$deck.Slides.Item(1).Shapes|Where-Object {$_.AlternativeText -like ('LayerDeck:'+$target.id+';*')}|Select-Object -First 1
  if(-not $shape -or -not $shape.HasTextFrame){throw 'PowerPoint native text missing'}
  $x=[double]$shape.Left+60;$y=[double]$shape.Top+90;$shape.Left=$x;$shape.Top=$y
  $deck.SaveAs((Join-Path $folder 'moved-text.pptx'));$deck.SaveCopyAs((Join-Path $folder 'moved-ppt.pdf'),32)
 }finally{$deck.Close()}
 $saved=$ppt.Presentations.Open((Join-Path $folder 'moved-text.pptx'),-1,0,0)
 try{
  $shape=$saved.Slides.Item(1).Shapes|Where-Object {$_.AlternativeText -like ('LayerDeck:'+$target.id+';*')}|Select-Object -First 1
  $checks+=@{format='pptx';id=$target.id;x=$x;y=$y;reopened=([Math]::Abs($shape.Left-$x) -lt .01 -and [Math]::Abs($shape.Top-$y) -lt .01)}
 }finally{$saved.Close()}
}finally{if($initial -eq 0 -and $ppt.Presentations.Count -eq 0){$ppt.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt)|Out-Null}
$word=New-Object -ComObject Word.Application;$initial=$word.Documents.Count;$alerts=$word.DisplayAlerts
try{
 $word.DisplayAlerts=0;$doc=$word.Documents.Open((Join-Path $folder 'converted.docx'),$false,$false,$false)
 try{
  $shape=$doc.Shapes.Item('layer_'+$target.id);$x=[double]$shape.Left+60;$y=[double]$shape.Top+90;$shape.Left=$x;$shape.Top=$y
  [object]$out=[string](Join-Path $folder 'moved-text.docx');[object]$fmt=[int]12;$doc.SaveAs([ref]$out,[ref]$fmt)
 }finally{$doc.Close(0)}
 $saved=$word.Documents.Open((Join-Path $folder 'moved-text.docx'),$false,$true,$false)
 try{
  $shape=$saved.Shapes.Item('layer_'+$target.id)
  $checks+=@{format='docx';id=$target.id;x=$x;y=$y;reopened=([Math]::Abs($shape.Left-$x) -lt .1 -and [Math]::Abs($shape.Top-$y) -lt .1)}
  [object]$out=[string](Join-Path $folder 'moved-word.pdf');[object]$fmt=[int]17;$saved.SaveAs([ref]$out,[ref]$fmt)
 }finally{$saved.Close(0)}
}finally{$word.DisplayAlerts=$alerts;if($initial -eq 0 -and $word.Documents.Count -eq 0){$word.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)|Out-Null}
$checks|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $folder 'movement-validation.json') -Encoding UTF8
if(@($checks|Where-Object {-not $_.reopened}).Count){throw 'Native text movement did not persist'}
Write-Output 'PowerPoint and Word native text moved, saved and reopened.'
