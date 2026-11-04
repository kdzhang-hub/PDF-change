param([Parameter(Mandatory=$true)][string]$Folder)
$ErrorActionPreference='Stop';$folder=(Resolve-Path -LiteralPath $Folder).Path
$target=(Get-Content -LiteralPath (Join-Path $folder 'logo-targets.json') -Raw -Encoding UTF8 | ConvertFrom-Json)[0]
$checks=@()
$ppt=New-Object -ComObject PowerPoint.Application;$initial=$ppt.Presentations.Count
try{
 $deck=$ppt.Presentations.Open((Join-Path $folder 'converted.pptx'),0,0,0)
 try{
  $shape=$null
  foreach($item in $deck.Slides.Item(1).Shapes){if($item.AlternativeText.StartsWith(('LayerDeck:'+$target.id+';'))){$shape=$item;break}}
  if(-not $shape -or $shape.Type -ne 13){throw 'Expected a native picture for the complete mark.'}
  $shape.LockAspectRatio=0;$shape.Left=$target.x+60;$shape.Top=$target.y+90;$shape.Width=$target.width*1.15;$shape.Height=$target.height*1.15
  $deck.SaveAs((Join-Path $folder 'moved-logo.pptx'))
 }finally{$deck.Close()}
 $deck=$ppt.Presentations.Open((Join-Path $folder 'moved-logo.pptx'),-1,0,0)
 try{
  $shape=$null
  foreach($item in $deck.Slides.Item(1).Shapes){if($item.AlternativeText.StartsWith(('LayerDeck:'+$target.id+';'))){$shape=$item;break}}
  $passed=$shape.Type -eq 13 -and [Math]::Abs($shape.Left-($target.x+60)) -lt .01 -and [Math]::Abs($shape.Top-($target.y+90)) -lt .01 -and [Math]::Abs($shape.Width-$target.width*1.15) -lt .01 -and [Math]::Abs($shape.Height-$target.height*1.15) -lt .01
  $checks+=@{format='pptx';nativePicture=$true;movedScaledReopened=$passed}
  $deck.SaveCopyAs((Join-Path $folder 'moved-logo-pptx.pdf'),32)
 }finally{$deck.Close()}
 $deck=$ppt.Presentations.Open((Join-Path $folder 'hidden-logo.pptx'),-1,0,0)
 try{$deck.SaveCopyAs((Join-Path $folder 'hidden-logo-pptx.pdf'),32)}finally{$deck.Close()}
}finally{if($initial -eq 0 -and $ppt.Presentations.Count -eq 0){$ppt.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt)|Out-Null}
$word=New-Object -ComObject Word.Application;$initial=$word.Documents.Count;$alerts=$word.DisplayAlerts
try{
 $word.DisplayAlerts=0
 $doc=$word.Documents.Open((Join-Path $folder 'converted.docx'),$false,$false,$false)
 try{
  $shape=$doc.Shapes.Item('layer_'+$target.id)
  if($shape.Type -ne 13){throw 'Word mark is not a native picture.'}
  $shape.LockAspectRatio=0;$shape.Left=$target.x+60;$shape.Top=$target.y+90;$shape.Width=$target.width*1.15;$shape.Height=$target.height*1.15
  [object]$file=[string](Join-Path $folder 'moved-logo.docx');[object]$format=[int]12;$doc.SaveAs([ref]$file,[ref]$format)
 }finally{$doc.Close(0)}
 $doc=$word.Documents.Open((Join-Path $folder 'moved-logo.docx'),$false,$true,$false)
 try{
  $shape=$doc.Shapes.Item('layer_'+$target.id)
  $passed=$shape.Type -eq 13 -and [Math]::Abs($shape.Left-($target.x+60)) -lt .1 -and [Math]::Abs($shape.Top-($target.y+90)) -lt .1 -and [Math]::Abs($shape.Width-$target.width*1.15) -lt .1 -and [Math]::Abs($shape.Height-$target.height*1.15) -lt .1
  $checks+=@{format='docx';nativePicture=$true;movedScaledReopened=$passed}
  [object]$file=[string](Join-Path $folder 'moved-logo-docx.pdf');[object]$format=[int]17;$doc.SaveAs([ref]$file,[ref]$format)
 }finally{$doc.Close(0)}
 $doc=$word.Documents.Open((Join-Path $folder 'hidden-logo.docx'),$false,$true,$false)
 try{[object]$file=[string](Join-Path $folder 'hidden-logo-docx.pdf');[object]$format=[int]17;$doc.SaveAs([ref]$file,[ref]$format)}finally{$doc.Close(0)}
}finally{$word.DisplayAlerts=$alerts;if($initial -eq 0 -and $word.Documents.Count -eq 0){$word.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)|Out-Null}
$checks|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $folder 'logo-movement-validation.json') -Encoding UTF8
if(@($checks|Where-Object {-not $_.movedScaledReopened}).Count){throw 'Mark move/scale/reopen failed.'}
Write-Output 'Complete mark stayed a movable native picture in PowerPoint and Word.'
