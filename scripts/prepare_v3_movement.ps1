param([string]$Folder='')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if(-not $Folder){$Folder=Join-Path $root 'deliverables\v3-movement-20261028'}
$folder=(Resolve-Path -LiteralPath $Folder).Path
$pages=@(1,2,4)
$moves=@(
 @{page=1;id=286;dx=8;dy=-5;role='small-label'},
 @{page=1;id=15;dx=-18;dy=-6;role='portrait'},
 @{page=1;id=9;dx=-12;dy=8;role='decoration'},
 @{page=2;id=253;dx=12;dy=3;role='title'},
 @{page=2;id=26;dx=6;dy=0;role='group'},
 @{page=4;id=210;dx=12;dy=-6;role='photo'},
 @{page=4;id=209;dx=-8;dy=4;role='body-text'},
 @{page=4;id=254;dx=14;dy=5;role='decoration'}
)
function Box($shape){return @([double]$shape.Left,[double]$shape.Top,[double]$shape.Width,[double]$shape.Height)}
$app=New-Object -ComObject PowerPoint.Application
$initial=$app.Presentations.Count
$records=@()
try{
 foreach($kind in @('ordinary','image')){
  $source=Join-Path $folder ($kind+'-source.pptx')
  $deck=$app.Presentations.Open($source,-1,0,0)
  try{
   $deck.SaveCopyAs((Join-Path $folder ($kind+'-source.pdf')),32)
   foreach($page in $pages){$deck.Slides.Item($page).Export((Join-Path $folder ($kind+'-before-'+$page+'.png')),'PNG',1200,675)}
  }finally{$deck.Close()}
  $copy=Join-Path $folder ($kind+'-moved.pptx')
  if(Test-Path -LiteralPath $copy){throw 'Movement output already exists; preserve the earlier run and choose a new folder.'}
  Copy-Item -LiteralPath $source -Destination $copy
  $deck=$app.Presentations.Open($copy,0,0,0)
  try{
   if($kind -eq 'ordinary'){
    foreach($move in $moves){
     $slide=$deck.Slides.Item($move.page)
     $shape=$null
     foreach($candidate in $slide.Shapes){if($candidate.Id -eq $move.id){$shape=$candidate;break}}
     if($null -eq $shape){throw ('Expected source object missing: '+$move.page+':'+$move.id)}
     $before=Box $shape
     $shape.Left=$shape.Left+$move.dx;$shape.Top=$shape.Top+$move.dy
     $records+=@{kind=$kind;page=$move.page;id=$move.id;name=$shape.Name;role=$move.role;before=$before;after=(Box $shape);text=if($shape.HasTextFrame){$shape.TextFrame.TextRange.Text}else{''}}
    }
   }else{
    foreach($page in $pages){
     $slide=$deck.Slides.Item($page)
     if($slide.Shapes.Count -ne 1){throw 'Image-only deck is not one object per slide as inventoried'}
     $shape=$slide.Shapes.Item(1);$before=Box $shape
     $shape.LockAspectRatio=-1;$shape.Width=$shape.Width*.95;$shape.Left=32;$shape.Top=18
     $records+=@{kind=$kind;page=$page;id=$shape.Id;name=$shape.Name;role='whole-page-image';before=$before;after=(Box $shape);text='';note='Whole image moved and proportionally reduced 5 percent to remain within slide; internal objects unavailable before reconstruction.'}
    }
   }
   $deck.Save()
   $deck.SaveCopyAs((Join-Path $folder ($kind+'-moved.pdf')),32)
   foreach($page in $pages){$deck.Slides.Item($page).Export((Join-Path $folder ($kind+'-after-'+$page+'.png')),'PNG',1200,675)}
  }finally{$deck.Close()}
 }
}finally{
 if($initial -eq 0 -and $app.Presentations.Count -eq 0){$app.Quit()}
 [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null
}
$records|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $folder 'source-movements.json') -Encoding UTF8
Write-Output ('Prepared both moved copies; movement records: '+$records.Count)
