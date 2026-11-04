param([Parameter(Mandatory=$true)][string]$Folder,[switch]$Edited)
$ErrorActionPreference='Stop';$folder=(Resolve-Path -LiteralPath $Folder).Path
$scene=(Get-Content -LiteralPath (Join-Path $folder 'scenes.json') -Raw -Encoding UTF8|ConvertFrom-Json)[0]
function Find-Layer($shapes,$id){
 foreach($shape in $shapes){
  if($shape.Type -eq 6){$found=Find-Layer $shape.GroupItems $id;if($found){return $found}}
  elseif($shape.AlternativeText -like ('LayerDeck:'+$id+';*')){return $shape}
 }
 return $null
}
$checks=@();$app=New-Object -ComObject PowerPoint.Application;$initial=$app.Presentations.Count
try{
 $filename=if($Edited){'all-native-fonts-edit-check.pptx'}else{'converted.pptx'}
 $deck=$app.Presentations.Open((Join-Path $folder $filename),-1,0,0)
 try{
  foreach($layer in $scene.layers){
   if($layer.kind -ne 'text' -or -not $layer.visible){continue}
   $shape=Find-Layer $deck.Slides.Item(1).Shapes $layer.id
   if(-not $shape -or -not $shape.HasTextFrame){throw 'Native text shape missing'}
   $actual=1-[double]$shape.TextFrame2.TextRange.Font.Fill.Transparency
   $checks+=@{id=$layer.id;text=$layer.text;expected=[double]$layer.opacity;actual=$actual;matches=([Math]::Abs($actual-[double]$layer.opacity) -lt .002)}
  }
 }finally{$deck.Close()}
}finally{if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
$output=if($Edited){'ppt-alpha-edited-validation.json'}else{'ppt-alpha-validation.json'}
$checks|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $folder $output) -Encoding UTF8
$failed=@($checks|Where-Object {-not $_.matches}).Count;Write-Output ('PowerPoint native alpha checks: '+$checks.Count+'; mismatches: '+$failed)
if($failed){throw 'PowerPoint text opacity did not match the saved scene'}
