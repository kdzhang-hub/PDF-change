param([string]$Round='11',[string]$Folder='')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if(-not $Folder){$folder=Join-Path $root ('deliverables\real-case-20261027\round-'+$Round)}else{$folder=(Resolve-Path -LiteralPath $Folder).Path}
$app=New-Object -ComObject PowerPoint.Application
$initial=$app.Presentations.Count
$tests=@()
function Get-LeafShapes($shapes){
 foreach($shape in $shapes){
  if($shape.Type -eq 6){Get-LeafShapes $shape.GroupItems}else{Write-Output $shape}
 }
}
try{
 $deck=$app.Presentations.Open((Join-Path $folder 'converted.pptx'),0,0,0)
 try{
  for($i=1;$i -le $deck.Slides.Count;$i++){
   foreach($shape in (Get-LeafShapes $deck.Slides.Item($i).Shapes)){
    if($shape.HasTextFrame -and $shape.TextFrame.HasText){
     $text=$shape.TextFrame.TextRange.Text
     $font=$shape.TextFrame.TextRange.Font
     $before=$font.Size
     $font.Name='Microsoft YaHei';$font.NameFarEast='Microsoft YaHei';$font.Size=$before+2
     $shape.TextFrame.TextRange.Text=$text+' *'
     $tests+=@{slide=$i;shapeId=$shape.Id;text=$text;expectedSize=$before+2;fontChanged=($font.Name -eq 'Microsoft YaHei');sizeChanged=([Math]::Abs($font.Size-($before+2)) -lt .01);textChanged=$shape.TextFrame.TextRange.Text.EndsWith('*')}
    }
   }
  }
  $deck.SaveAs((Join-Path $folder 'all-native-fonts-edit-check.pptx'))
  $deck.Slides.Item(1).Export((Join-Path $folder 'all-native-fonts-edit-check.png'),'PNG',1200,675)
 }finally{$deck.Close()}
 $saved=$app.Presentations.Open((Join-Path $folder 'all-native-fonts-edit-check.pptx'),-1,0,0)
 try{
  foreach($test in $tests){
   $shape=Get-LeafShapes $saved.Slides.Item($test.slide).Shapes | Where-Object {$_.Id -eq $test.shapeId} | Select-Object -First 1
   if($null -eq $shape){$test.reopened=$false;continue}
   $range=$shape.TextFrame.TextRange
   $test.reopened=($range.Text -eq ($test.text+' *') -and $range.Font.NameFarEast -eq 'Microsoft YaHei' -and [Math]::Abs($range.Font.Size-$test.expectedSize) -lt .01)
  }
 }finally{$saved.Close()}
}finally{if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
$tests|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $folder 'font-edit-validation.json') -Encoding UTF8
Write-Output ('Changed text, font and size on '+$tests.Count+' native text objects.')
if($tests.Count -eq 0 -or @($tests|Where-Object {-not $_.fontChanged -or -not $_.sizeChanged -or -not $_.textChanged -or -not $_.reopened}).Count){throw 'Font editing or saved-deck reopen validation failed'}
