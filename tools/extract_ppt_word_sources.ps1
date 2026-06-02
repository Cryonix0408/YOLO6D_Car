param(
    [Parameter(Mandatory = $true)][string]$PptxPath,
    [Parameter(Mandatory = $true)][string]$DocxPath,
    [Parameter(Mandatory = $true)][string]$OutputDir
)

$ErrorActionPreference = "Stop"
$null = New-Item -ItemType Directory -Path $OutputDir -Force
$slidesDir = Join-Path $OutputDir "slides"
$null = New-Item -ItemType Directory -Path $slidesDir -Force

$ppt = $null
$presentation = $null
$word = $null
$doc = $null

try {
    $ppt = New-Object -ComObject PowerPoint.Application
    $presentation = $ppt.Presentations.Open($PptxPath, $true, $false, $false)
    $slideRows = @()

    foreach ($slide in $presentation.Slides) {
        $slideNumber = [int]$slide.SlideIndex
        $imagePath = Join-Path $slidesDir ("slide_{0:D2}.png" -f $slideNumber)
        $slide.Export($imagePath, "PNG", 1280, 720)

        $texts = New-Object System.Collections.Generic.List[string]
        foreach ($shape in $slide.Shapes) {
            try {
                if ($shape.HasTextFrame -and $shape.TextFrame.HasText) {
                    $text = [string]$shape.TextFrame.TextRange.Text
                    $text = $text.Trim()
                    if ($text.Length -gt 0) {
                        $texts.Add($text)
                    }
                }
            } catch {
            }
        }

        $slideRows += [pscustomobject]@{
            slide_index = $slideNumber
            image_path = $imagePath
            text = ($texts -join "`n")
        }
    }
    $presentation.Close()
    $presentation = $null
    $ppt.Quit()
    $ppt = $null

    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $doc = $word.Documents.Open($DocxPath, $false, $true)
    $paragraphRows = @()
    $paragraphIndex = 0
    foreach ($paragraph in $doc.Paragraphs) {
        $text = [string]$paragraph.Range.Text
        $text = $text -replace "`r", ""
        $text = $text.Trim()
        if ($text.Length -eq 0) {
            continue
        }
        $paragraphIndex += 1
        $styleName = ""
        try {
            $styleName = [string]$paragraph.Style.NameLocal
        } catch {
            $styleName = ""
        }
        $paragraphRows += [pscustomobject]@{
            paragraph_index = $paragraphIndex
            style = $styleName
            text = $text
        }
    }
    $doc.Close($false)
    $doc = $null
    $word.Quit()
    $word = $null

    $payload = [pscustomobject]@{
        pptx_path = $PptxPath
        docx_path = $DocxPath
        slides = $slideRows
        paragraphs = $paragraphRows
    }
    $jsonPath = Join-Path $OutputDir "extracted_sources.json"
    $payload | ConvertTo-Json -Depth 8 | Set-Content -Path $jsonPath -Encoding UTF8
    Write-Output $jsonPath
} finally {
    if ($doc -ne $null) { $doc.Close($false) | Out-Null }
    if ($word -ne $null) { $word.Quit() | Out-Null }
    if ($presentation -ne $null) { $presentation.Close() | Out-Null }
    if ($ppt -ne $null) { $ppt.Quit() | Out-Null }
}
