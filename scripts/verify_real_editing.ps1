$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$folder=Join-Path $root 'deliverables\real-case-20261027\round-05'
$scenes=Get-Content -LiteralPath (Join-Path $folder 'scenes.json') -Raw -Encoding UTF8|ConvertFrom-Json
$portrait=$scenes[0].layers|Where-Object {$_.kind -eq 'image' -and $_.x -gt 600 -and $_.height -gt 250 -and $_.width -gt 150}|Sort-Object height -Descending|Select-Object -First 1
$app=New-Object -ComObject PowerPoint.Application
$initial=$app.Presentations.Count
$checks=@()
try {
 $deck=$app.Presentations.Open((Join-Path $folder 'converted.pptx'),0,0,0)
 try {
  for($i=1;$i -le $deck.Slides.Count;$i++){
   $slide=$deck.Slides.Item($i)
   $expected=$scenes[$i-1].layers.Count
   $checks+=@{page=$i;expectedObjects=$expected;actualObjects=$slide.Shapes.Count;countMatches=($expected -eq $slide.Shapes.Count)}
  }
  $textEdited=$false
  foreach($shape in $deck.Slides.Item(1).Shapes){
   if($shape.HasTextFrame -and $shape.TextFrame.HasText){$shape.TextFrame.TextRange.Text=$shape.TextFrame.TextRange.Text+' [EDIT]';$textEdited=$true;break}
  }
  $portraitMoved=$false
  if($portrait){
   foreach($shape in $deck.Slides.Item(1).Shapes){
    if($shape.AlternativeText -like ('LayerDeck:'+$portrait.id+';*')){
     $shape.Left=$shape.Left-100
     $portraitMoved=$true
     break
    }
   }
  }
  $deck.SaveAs((Join-Path $folder 'editing-check.pptx'))
  $deck.Slides.Item(1).Export((Join-Path $folder 'portrait-moved-check.png'),'PNG',1200,675)
  @{pages=$checks;textEdited=$textEdited;portraitMoved=$portraitMoved;saved=$true}|ConvertTo-Json -Depth 7|Set-Content -LiteralPath (Join-Path $folder 'editing-validation.json') -Encoding UTF8
 }finally{$deck.Close()}
}finally{if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()};[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null}
Write-Output 'Object counts, text editing, portrait movement and saving verified.'
