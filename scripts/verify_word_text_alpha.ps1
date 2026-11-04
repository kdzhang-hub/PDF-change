param([Parameter(Mandatory=$true)][string]$Folder,[switch]$AllowMismatch,[switch]$Edited)
$ErrorActionPreference='Stop';$folder=(Resolve-Path -LiteralPath $Folder).Path
$scenes=Get-Content -LiteralPath (Join-Path $folder 'scenes.json') -Raw -Encoding UTF8|ConvertFrom-Json
$checks=@();$word=New-Object -ComObject Word.Application;$initial=$word.Documents.Count;$alerts=$word.DisplayAlerts
try{
 $filename=if($Edited){'word-font-edit-check.docx'}else{'converted.docx'}
 $word.DisplayAlerts=0;$doc=$word.Documents.Open((Join-Path $folder $filename),$false,$true,$false)
 try{
  foreach($scene in $scenes){foreach($layer in $scene.layers){
   if($layer.kind -ne 'text' -or -not $layer.visible){continue}
   $shape=$doc.Shapes.Item('layer_'+$layer.id);$range=$shape.TextFrame.TextRange
   if($range.Text.EndsWith([string][char]13)){$range.End=$range.End-1}
   $actual=1-[double]$range.Font.Fill.Transparency
   $checks+=@{id=$layer.id;text=$layer.text;expected=[double]$layer.opacity;actual=$actual;matches=([Math]::Abs($actual-[double]$layer.opacity) -lt .002)}
  }}
 }finally{$doc.Close(0)}
}finally{$word.DisplayAlerts=$alerts;if($initial -eq 0 -and $word.Documents.Count -eq 0){$word.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)|Out-Null}
$output=if($Edited){'word-alpha-edited-validation.json'}else{'word-alpha-validation.json'}
$checks|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $folder $output) -Encoding UTF8
$failed=@($checks|Where-Object {-not $_.matches}).Count;Write-Output ('Word native alpha checks: '+$checks.Count+'; mismatches: '+$failed)
if($failed -and -not $AllowMismatch){throw 'Word text opacity did not match the saved scene'}
