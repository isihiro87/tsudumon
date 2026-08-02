Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'

$canvasWidth = 1080
$canvasHeight = 1920
$background = [System.Drawing.ColorTranslator]::FromHtml('#f6f6f4')
$black = [System.Drawing.Color]::Black
$white = [System.Drawing.Color]::White
$gray = [System.Drawing.ColorTranslator]::FromHtml('#707070')
$fontFamily = New-Object System.Drawing.FontFamily('Yu Gothic')

$generatedDir = 'C:\Users\user\.codex\generated_images\019fa7d1-351d-7600-9d81-ed602220faa9'
$sources = @{
    a = Join-Path $generatedDir 'call_OrX1sFEEVrgoKYJ2ujF3q94e.png'
    b = Join-Path $generatedDir 'call_rUnrAXkvBHH0Ed3g7GJyboBl.png'
    c = Join-Path $generatedDir 'call_AJx16NS1XYX86IlC0th5r7fV.png'
}

$outputDir = Join-Path $PSScriptRoot 'assets'
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

function New-Font([float]$size) {
    return New-Object System.Drawing.Font(
        $fontFamily,
        $size,
        [System.Drawing.FontStyle]::Bold,
        [System.Drawing.GraphicsUnit]::Pixel
    )
}

function Draw-Text(
    [System.Drawing.Graphics]$graphics,
    [string]$text,
    [float]$x,
    [float]$y,
    [float]$size,
    [System.Drawing.Color]$color
) {
    $font = New-Font $size
    $brush = New-Object System.Drawing.SolidBrush($color)
    $format = New-Object System.Drawing.StringFormat
    $format.FormatFlags = [System.Drawing.StringFormatFlags]::NoWrap
    $format.Trimming = [System.Drawing.StringTrimming]::None
    $graphics.DrawString($text, $font, $brush, $x, $y, $format)
    $format.Dispose()
    $brush.Dispose()
    $font.Dispose()
}

function Get-InkBounds([System.Drawing.Bitmap]$source) {
    $minX = $source.Width
    $minY = $source.Height
    $maxX = -1
    $maxY = -1

    for ($y = 0; $y -lt $source.Height; $y += 2) {
        for ($x = 0; $x -lt $source.Width; $x += 2) {
            $pixel = $source.GetPixel($x, $y)
            $luma = (0.2126 * $pixel.R) + (0.7152 * $pixel.G) + (0.0722 * $pixel.B)
            if ($luma -lt 145) {
                if ($x -lt $minX) { $minX = $x }
                if ($y -lt $minY) { $minY = $y }
                if ($x -gt $maxX) { $maxX = $x }
                if ($y -gt $maxY) { $maxY = $y }
            }
        }
    }

    if ($maxX -lt 0) { return $null }
    return New-Object System.Drawing.Rectangle(
        [Math]::Max(0, $minX - 8),
        [Math]::Max(0, $minY - 8),
        [Math]::Min($source.Width - $minX + 8, $maxX - $minX + 17),
        [Math]::Min($source.Height - $minY + 8, $maxY - $minY + 17)
    )
}

function Draw-Generated-LineArt(
    [System.Drawing.Graphics]$graphics,
    [string]$sourcePath,
    [int]$targetWidth,
    [int]$centerY
) {
    $source = New-Object System.Drawing.Bitmap($sourcePath)
    $bounds = Get-InkBounds $source
    if ($null -eq $bounds) {
        $source.Dispose()
        throw "No line art found in $sourcePath"
    }

    $targetHeight = [int][Math]::Round($targetWidth * $bounds.Height / $bounds.Width)
    $targetX = [int][Math]::Round(($canvasWidth - $targetWidth) / 2)
    $targetY = [int][Math]::Round($centerY - ($targetHeight / 2))
    $dest = New-Object System.Drawing.Rectangle($targetX, $targetY, $targetWidth, $targetHeight)

    $ink = New-Object System.Drawing.Bitmap(
        $bounds.Width,
        $bounds.Height,
        [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
    )
    for ($iy = 0; $iy -lt $bounds.Height; $iy++) {
        for ($ix = 0; $ix -lt $bounds.Width; $ix++) {
            $pixel = $source.GetPixel($bounds.X + $ix, $bounds.Y + $iy)
            $luma = (0.2126 * $pixel.R) + (0.7152 * $pixel.G) + (0.0722 * $pixel.B)
            if (($pixel.A -gt 0) -and ($luma -lt 170)) {
                $alpha = [int][Math]::Min(
                    255,
                    [Math]::Max(0, (170 - $luma) * 2.84 * ($pixel.A / 255.0))
                )
                $ink.SetPixel($ix, $iy, [System.Drawing.Color]::FromArgb($alpha, 0, 0, 0))
            }
        }
    }

    $graphics.DrawImage(
        $ink,
        $dest,
        0,
        0,
        $bounds.Width,
        $bounds.Height,
        [System.Drawing.GraphicsUnit]::Pixel
    )

    $ink.Dispose()
    $source.Dispose()
}

foreach ($variant in @('a', 'b', 'c')) {
    if (-not (Test-Path $sources[$variant])) {
        throw "Missing generated image: $($sources[$variant])"
    }

    $bitmap = New-Object System.Drawing.Bitmap($canvasWidth, $canvasHeight)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.Clear($background)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

    # The seven text elements below are deliberately identical across all variants.
    Draw-Text $graphics '【おわび】' 105 445 44 $black
    # 配信はこの時点でまだ止まったままなので、過去形にしない（現在形で書く）。
    Draw-Text $graphics 'いま、公式LINEの' 105 520 68 $black
    Draw-Text $graphics '配信が止まっています。' 105 625 68 $black
    Draw-Text $graphics 'ひと月に送れる通数の上限に' 105 750 41 $black
    Draw-Text $graphics '達してしまったためです。' 105 820 41 $black

    $band = New-Object System.Drawing.Rectangle(105, 915, 700, 92)
    $bandBrush = New-Object System.Drawing.SolidBrush($black)
    $graphics.FillRectangle($bandBrush, $band)
    $bandBrush.Dispose()
    Draw-Text $graphics '8月から、また届けます。' 125 928 49 $white
    Draw-Text $graphics '楽しみに待ってくれていた人、ごめんなさい。' 105 1045 31 $gray

    if ($variant -eq 'b') {
        Draw-Generated-LineArt $graphics $sources[$variant] 185 1370
    }
    elseif ($variant -eq 'c') {
        Draw-Generated-LineArt $graphics $sources[$variant] 290 1370
    }

    $graphics.Dispose()
    $outputPath = Join-Path $outputDir "punch-s1-0-$variant.png"
    $bitmap.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
}

$fontFamily.Dispose()
