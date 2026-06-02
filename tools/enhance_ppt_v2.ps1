param(
    [string]$SourcePptx = "C:\Users\25701\Desktop\YOLOv8Pose_FastMoving_1hour_Beautified.pptx",
    [string]$AdditionsJson = "D:\YOLO6D_Car\outputs\lecture_handout_work\ppt_v2_assets\ppt_v2_additions.json",
    [string]$OutputPptx = "D:\YOLO6D_Car\outputs\lecture_handout_work\YOLOv8Pose_FastMoving_1hour_Optimized_v2.pptx"
)

function OleColor([int]$r, [int]$g, [int]$b) {
    return ($r + ($g * 256) + ($b * 65536))
}

function Set-TextStyle($shape, [string]$fontName, [double]$fontSize, [int]$color, [bool]$bold) {
    $shape.TextFrame2.TextRange.Font.Name = $fontName
    $shape.TextFrame2.TextRange.Font.Size = $fontSize
    if ($bold) {
        $shape.TextFrame2.TextRange.Font.Bold = -1
    }
    else {
        $shape.TextFrame2.TextRange.Font.Bold = 0
    }
    $shape.TextFrame2.TextRange.Font.Fill.ForeColor.RGB = $color
    $shape.TextFrame2.MarginLeft = 0
    $shape.TextFrame2.MarginRight = 0
    $shape.TextFrame2.MarginTop = 0
    $shape.TextFrame2.MarginBottom = 0
}

$msoFalse = 0
$msoTrue = -1
$msoShapeRectangle = 1
$msoTextOrientationHorizontal = 1

$items = Get-Content -LiteralPath $AdditionsJson -Raw -Encoding UTF8 | ConvertFrom-Json

$powerPoint = New-Object -ComObject PowerPoint.Application
$powerPoint.Visible = $msoTrue

$presentation = $null
try {
    $presentation = $powerPoint.Presentations.Open($SourcePptx, $msoFalse, $msoFalse, $msoTrue)
    $slideWidth = [double]$presentation.PageSetup.SlideWidth
    $slideHeight = [double]$presentation.PageSetup.SlideHeight

    foreach ($item in $items) {
        $slideIndex = [int]$item.slide
        $slide = $presentation.Slides.Item($slideIndex)

        if ($item.has_formula -and $item.formula_image) {
            $panelLeft = 58
            $panelTop = $slideHeight - 126
            $panelWidth = $slideWidth - 116
            $panelHeight = 102
            $panel = $slide.Shapes.AddShape($msoShapeRectangle, $panelLeft, $panelTop, $panelWidth, $panelHeight)
            $panel.Fill.Solid()
            $panel.Fill.ForeColor.RGB = (OleColor 6 31 51)
            $panel.Fill.Transparency = 0.08
            $panel.Line.ForeColor.RGB = (OleColor 34 211 238)
            $panel.Line.Transparency = 0.2
            $panel.Line.Weight = 1.2

            $label = $slide.Shapes.AddTextbox($msoTextOrientationHorizontal, ($panelLeft + 18), ($panelTop + 10), 210, 22)
            $label.TextFrame2.TextRange.Text = "CORE FORMULA"
            Set-TextStyle $label "Aptos Display" 10 (OleColor 250 204 21) $true

            $formulaPath = [string]$item.formula_image
            if (Test-Path -LiteralPath $formulaPath) {
                $null = $slide.Shapes.AddPicture($formulaPath, $msoFalse, $msoTrue, ($panelLeft + 16), ($panelTop + 34), 520, 58)
            }

            $takeaway = $slide.Shapes.AddTextbox($msoTextOrientationHorizontal, ($panelLeft + 560), ($panelTop + 28), ($panelWidth - 590), 60)
            $takeaway.TextFrame2.TextRange.Text = [string]$item.takeaway
            Set-TextStyle $takeaway "Microsoft YaHei" 13 (OleColor 226 232 240) $false
        }
        else {
            $barLeft = 58
            $barTop = $slideHeight - 76
            $barWidth = $slideWidth - 116
            $bar = $slide.Shapes.AddShape($msoShapeRectangle, $barLeft, $barTop, $barWidth, 44)
            $bar.Fill.Solid()
            $bar.Fill.ForeColor.RGB = (OleColor 6 31 51)
            $bar.Fill.Transparency = 0.18
            $bar.Line.ForeColor.RGB = (OleColor 34 211 238)
            $bar.Line.Transparency = 0.35
            $bar.Line.Weight = 1

            $text = $slide.Shapes.AddTextbox($msoTextOrientationHorizontal, ($barLeft + 22), ($barTop + 10), ($barWidth - 42), 28)
            $text.TextFrame2.TextRange.Text = [string]$item.takeaway
            Set-TextStyle $text "Microsoft YaHei" 14 (OleColor 226 232 240) $false

            $accent = $slide.Shapes.AddShape($msoShapeRectangle, ($barLeft + 5), ($barTop + 10), 4, 25)
            $accent.Fill.Solid()
            $accent.Fill.ForeColor.RGB = (OleColor 34 211 238)
            $accent.Line.Visible = $msoFalse
        }
    }

    $outDir = Split-Path -Parent $OutputPptx
    if (-not (Test-Path -LiteralPath $outDir)) {
        New-Item -ItemType Directory -Path $outDir | Out-Null
    }
    if (Test-Path -LiteralPath $OutputPptx) {
        Remove-Item -LiteralPath $OutputPptx -Force
    }
    $presentation.SaveAs($OutputPptx)
    Write-Output $OutputPptx
}
finally {
    if ($presentation -ne $null) {
        $presentation.Close()
    }
    $powerPoint.Quit()
}
