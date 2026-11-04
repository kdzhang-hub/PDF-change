$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$deliveries = Join-Path $projectRoot 'deliverables'
$office = New-Object -ComObject PowerPoint.Application
$initialCount = $office.Presentations.Count
$results = @()
try {
    foreach ($stem in @('digital', 'scanned')) {
        $inputPath = Join-Path $deliveries ($stem + '.pptx')
        if (-not (Test-Path -LiteralPath $inputPath)) { continue }
        $deck = $office.Presentations.Open($inputPath, 0, 0, 0)
        try {
            $deck.SaveCopyAs((Join-Path $deliveries ($stem + '-powerpoint.pdf')), 32)
            $counts = @()
            for ($i = 1; $i -le $deck.Slides.Count; $i++) {
                $slide = $deck.Slides.Item($i)
                $slide.Export((Join-Path $deliveries ($stem + '-page-' + $i + '.png')), 'PNG', 1440, 810)
                $counts += $slide.Shapes.Count
            }
            $textEdited = $false
            foreach ($shape in $deck.Slides.Item(1).Shapes) {
                if ($shape.HasTextFrame -and $shape.TextFrame.HasText) {
                    $shape.TextFrame.TextRange.Text = $shape.TextFrame.TextRange.Text + ' [EDIT TEST]'
                    $textEdited = $true
                    break
                }
            }
            $moved = $deck.Slides.Item(1).Shapes.Item(1)
            $oldLeft = $moved.Left
            $moved.Left = $oldLeft + 12
            $copyPath = Join-Path $deliveries ($stem + '-edited-test.pptx')
            $deck.SaveAs($copyPath)
            $deck.Slides.Item(1).Export((Join-Path $deliveries ($stem + '-edited-test.png')), 'PNG', 1440, 810)
            $results += @{file=$stem; opened=$true; shapeCounts=$counts; textEdited=$textEdited; objectMoved=($moved.Left -eq ($oldLeft + 12)); saved=$true}
        } finally { $deck.Close() }
    }
} finally {
    if ($initialCount -eq 0 -and $office.Presentations.Count -eq 0) { $office.Quit() }
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($office) | Out-Null
}
$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $deliveries 'powerpoint-validation.json') -Encoding utf8
$results | ConvertTo-Json -Depth 5
