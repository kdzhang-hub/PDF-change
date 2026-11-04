param([Parameter(Mandatory=$true)][string]$Folder,[ValidateSet('pptx','docx')][string]$Kind)
$ErrorActionPreference='Stop'
$folder=(Resolve-Path -LiteralPath $Folder).Path
if($Kind -eq 'pptx'){
 $app=New-Object -ComObject PowerPoint.Application;$initial=$app.Presentations.Count
 try{
  $deck=$app.Presentations.Open((Join-Path $folder 'converted.pptx'),-1,0,0)
  try{$deck.SaveCopyAs((Join-Path $folder 'powerpoint.pdf'),32)}finally{$deck.Close()}
 }finally{if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()};[Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
}else{
 $app=New-Object -ComObject Word.Application;$initial=$app.Documents.Count;$alerts=$app.DisplayAlerts
 try{
  $app.DisplayAlerts=0
  $doc=$app.Documents.Open((Join-Path $folder 'converted.docx'),$false,$true,$false)
  try{[object]$file=[string](Join-Path $folder 'word-render.pdf');[object]$format=[int]17;$doc.SaveAs([ref]$file,[ref]$format)}finally{$doc.Close(0)}
 }finally{$app.DisplayAlerts=$alerts;if($initial -eq 0 -and $app.Documents.Count -eq 0){$app.Quit()};[Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
}
