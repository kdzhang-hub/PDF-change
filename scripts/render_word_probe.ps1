param([Parameter(Mandatory=$true)][string]$Folder)
$ErrorActionPreference='Stop'
$folder=(Resolve-Path -LiteralPath $Folder).Path
$app=New-Object -ComObject Word.Application
$initial=$app.Documents.Count;$alerts=$app.DisplayAlerts;$screen=$app.ScreenUpdating
try{
 $app.DisplayAlerts=0;$app.ScreenUpdating=$false
 $doc=$app.Documents.Open((Join-Path $folder 'probe.docx'),$false,$true,$false)
 try{
  $doc.Repaginate()
  [object]$pdf=[string](Join-Path $folder 'probe.pdf');[object]$format=[int]17
  $doc.SaveAs([ref]$pdf,[ref]$format)
 }finally{$doc.Close(0)}
}finally{
 $app.DisplayAlerts=$alerts;$app.ScreenUpdating=$screen
 if($initial -eq 0 -and $app.Documents.Count -eq 0){$app.Quit()}
 [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null
}
