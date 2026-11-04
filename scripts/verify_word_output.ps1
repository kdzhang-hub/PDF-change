param([Parameter(Mandatory=$true)][string]$Folder,[switch]$SkipRender)
$ErrorActionPreference='Stop';$folder=(Resolve-Path -LiteralPath $Folder).Path
Write-Output 'Starting local Word COM.'
$app=New-Object -ComObject Word.Application;$initial=$app.Documents.Count;$alerts=$app.DisplayAlerts
Write-Output 'Word COM connected.'
$checks=@()
try{
 $app.DisplayAlerts=0
 $app.ScreenUpdating=$false
 Write-Output 'Opening converted DOCX.'
 $doc=$app.Documents.Open((Join-Path $folder 'converted.docx'),$false,$false,$false)
 Write-Output 'Converted DOCX opened.'
 try{
  $doc.Repaginate();$pages=$doc.ComputeStatistics(2)
  Write-Output ('Native Word objects: '+$doc.Shapes.Count)
  foreach($shape in $doc.Shapes){
   if($checks.Count -eq 0){Write-Output ('Inspecting '+$shape.Name+' type '+$shape.Type)}
   if($shape.Type -eq 15){
    $text=$shape.TextEffect.Text;$size=$shape.TextEffect.FontSize
    $shape.TextEffect.Text=$text.TrimEnd()+' *';$shape.TextEffect.FontName='Microsoft YaHei';$shape.TextEffect.FontSize=$size+1
    $checks+=@{name=$shape.Name;text=$text;size=$size+1;expected=$shape.TextEffect.Text;wordArt=$true;reopened=$false}
   }elseif($shape.TextFrame.HasText -ne 0){
    $range=$shape.TextFrame.TextRange
    if($range.Text.EndsWith([string][char]13)){$range.End=$range.End-1}
    $text=$range.Text;$size=$range.Font.Size
    if($size -gt 1000 -or $size -le 0){$size=$range.Characters.Item(1).Font.Size}
    if($checks.Count -eq 0){Write-Output ('First text range read; size '+$size)}
    $range.Text=$text.TrimEnd()+ ' *'
    $range.Font.Name='Microsoft YaHei';$range.Font.NameFarEast='Microsoft YaHei';$range.Font.Size=$size+1
    $checks+=@{name=$shape.Name;text=$text;size=$size+1;expected=$range.Text;reopened=$false}
    if($checks.Count % 10 -eq 0){Write-Output ('Edited '+$checks.Count+' Word text boxes.')}
   }
  }
  [object]$savePath=[string](Join-Path $folder 'word-font-edit-check.docx');[object]$saveFormat=[int]12
  $doc.SaveAs([ref]$savePath,[ref]$saveFormat)
  Write-Output 'Text edits saved.'
 }finally{$doc.Close(0)}
 $saved=$app.Documents.Open((Join-Path $folder 'word-font-edit-check.docx'),$false,$true,$false)
 try{
  foreach($check in $checks){
   $shape=$saved.Shapes.Item($check.name)
   if($check.wordArt){$check.actualText=$shape.TextEffect.Text;$check.actualFont=$shape.TextEffect.FontName;$check.actualSize=$shape.TextEffect.FontSize}
   else{
    $range=$shape.TextFrame.TextRange
    if($range.Text.EndsWith([string][char]13)){$range.End=$range.End-1}
    $check.actualText=$range.Text;$check.actualFont=$range.Font.NameFarEast;$check.actualSize=$range.Font.Size
   }
   $check.reopened=($check.actualText -eq $check.expected -and $check.actualFont -in @('Microsoft YaHei','微软雅黑') -and [Math]::Abs($check.actualSize-$check.size) -lt .01)
  }
 }finally{$saved.Close(0)}
 @{objects=$checks.Count;checks=$checks}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $folder 'word-font-validation.json') -Encoding UTF8
 if(-not $SkipRender){
 $render=$app.Documents.Open((Join-Path $folder 'converted.docx'),$false,$true,$false)
 try{
  Write-Output 'Rendering original converted DOCX.'
  [object]$pdfPath=[string](Join-Path $folder 'word-render.pdf');[object]$pdfFormat=[int]17
  $render.SaveAs([ref]$pdfPath,[ref]$pdfFormat)
  Write-Output 'Word PDF rendering completed.'
 }finally{$render.Close(0)}
 }
}finally{$app.ScreenUpdating=$true;$app.DisplayAlerts=$alerts;if($initial -eq 0 -and $app.Documents.Count -eq 0){$app.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
@{pages=$pages;objects=$checks.Count;checks=$checks}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $folder 'word-validation.json') -Encoding UTF8
if(-not $checks.Count -or @($checks|Where-Object {-not $_.reopened}).Count){throw 'Word native text edit/reopen failed'}
Write-Output ('Word rendered '+$pages+' pages; '+$checks.Count+' native text objects edited and reopened.')
