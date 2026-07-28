Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'
$richmenuDir = Join-Path $PSScriptRoot '..\richmenu'
$workDir = Join-Path $richmenuDir '.parent-work'
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

$W = 2500
$H = 1686
$X = @(0, 833, 1666, 2500)
$Y = @(0, 843, 1686)
$fontBold = 'C:\Windows\Fonts\UDDigiKyokashoN-B.ttc'
$fontRegular = 'C:\Windows\Fonts\UDDigiKyokashoN-R.ttc'

function HexColor([string]$hex, [int]$alpha = 255) {
    $opaque = [System.Drawing.ColorTranslator]::FromHtml($hex)
    [System.Drawing.Color]::FromArgb($alpha, $opaque.R, $opaque.G, $opaque.B)
}

function Rect([float]$x, [float]$y, [float]$w, [float]$h) {
    [System.Drawing.RectangleF]::new($x, $y, $w, $h)
}

function U([string]$base64) {
    [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($base64))
}

function RoundedPath([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $d = 2 * $r
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    $path
}

function DrawCenteredText(
    $graphics, [string]$text, [string]$fontFile, [float]$size,
    [string]$hex, [float]$x, [float]$y, [float]$w, [float]$h
) {
    $fonts = [System.Drawing.Text.PrivateFontCollection]::new()
    $fonts.AddFontFile($fontFile)
    $font = [System.Drawing.Font]::new(
        $fonts.Families[0], $size, [System.Drawing.FontStyle]::Regular,
        [System.Drawing.GraphicsUnit]::Pixel
    )
    $brush = [System.Drawing.SolidBrush]::new((HexColor $hex))
    $format = [System.Drawing.StringFormat]::new()
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $format.FormatFlags = [System.Drawing.StringFormatFlags]::NoWrap
    $graphics.DrawString($text, $font, $brush, (Rect $x $y $w $h), $format)
    $format.Dispose()
    $brush.Dispose()
    $font.Dispose()
    $fonts.Dispose()
}

function DrawMarker($graphics, [float]$x1, [float]$x2, [float]$y, [string]$hex) {
    $pen = [System.Drawing.Pen]::new((HexColor $hex 190), 18)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $graphics.DrawLine($pen, $x1, $y, $x2, $y)
    $pen.Dispose()
}

function DrawDots($graphics, [float]$x1, [float]$x2, [float]$y, [string]$hex) {
    $brush = [System.Drawing.SolidBrush]::new((HexColor $hex 210))
    for ($x = $x1; $x -le $x2; $x += 38) {
        $graphics.FillEllipse($brush, $x, $y, 8, 8)
    }
    $brush.Dispose()
}

$items = @(
    @{ label = (U '5a2m57+S44Gu6KiY6Yyy');             sub = (U '44GK5a2Q44GV44G+44Gu5Y+W44KK57WE44G/');     size = 94 },
    @{ label = (U '44GK5pSv5omV44GE44O76Kej57SE');     sub = (U '44GE44Gk44Gn44KC44GK5omL57aa44GN');       size = 88 },
    @{ label = (U '44KI44GP44GC44KL6LOq5ZWP');         sub = (U '5paZ6YeR44O76YCa55+l44O75a6J5YWo5oCn');     size = 94 },
    @{ label = (U '44GK5a2Q44GV44KT44Gu6L+95Yqg');     sub = (U '44GN44KH44GG44Gg44GE44KC44Gk44Gq44GS44G+44GZ'); size = 86 },
    @{ label = (U '44K144O844OT44K544Gu6Kqs5piO');     sub = (U '44Gp44KT44Gq5pWZ5p2Q77yf');                 size = 86 },
    @{ label = (U '6YGL5Za244Gr55u46KuH44GZ44KL');     sub = (U '5Lq644GM44GK6L+U5LqL44GX44G+44GZ');         size = 88 }
)

$designs = @(
    @{
        name = 'a'; source = 'parent-a-generated.png'
        panel = '#fff8e8'; panelAlpha = 247; outline = '#dc8b28'
        label = '#d95f02'; sub = '#6f3014'; divider = '#df7208'
        marker = '#ffd24f'; colors = 32; rounded = $true; panelY = 492
    },
    @{
        name = 'b'; source = 'parent-b-generated.png'
        panel = '#fffaf0'; panelAlpha = 244; outline = '#e7b96c'
        label = '#d85d02'; sub = '#603018'; divider = '#dc7108'
        marker = '#ffd75d'; colors = 36; rounded = $false; panelY = 430
    }
)

foreach ($design in $designs) {
    $sourcePath = Join-Path $richmenuDir $design.source
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        throw "Missing generated visual: $sourcePath"
    }

    $source = [System.Drawing.Image]::FromFile($sourcePath)
    $bitmap = [System.Drawing.Bitmap]::new(
        $W, $H, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb
    )
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

    # Center-crop the 3:2 generated source to the requested 2500:1686 aspect.
    $cropW = [float]($source.Height * $W / $H)
    $cropX = [float](($source.Width - $cropW) / 2)
    $dest = [System.Drawing.RectangleF]::new(0, 0, $W, $H)
    $src = [System.Drawing.RectangleF]::new($cropX, 0, $cropW, $source.Height)
    $graphics.DrawImage($source, $dest, $src, [System.Drawing.GraphicsUnit]::Pixel)
    $source.Dispose()

    for ($i = 0; $i -lt 6; $i++) {
        $row = [int][Math]::Floor($i / 3.0)
        $col = $i % 3
        $x0 = $X[$col]
        $y0 = $Y[$row]
        $cellW = $X[$col + 1] - $x0
        $panelX = $x0 + 30
        $panelY = $y0 + $design.panelY
        $panelW = $cellW - 60
        $panelH = 814 - $design.panelY

        $panelHex = if ($i -eq 0) { '#f79a12' } else { $design.panel }
        $panelAlpha = if ($i -eq 0) { 255 } else { $design.panelAlpha }
        $panelBrush = [System.Drawing.SolidBrush]::new((HexColor $panelHex $panelAlpha))

        if ($design.rounded) {
            $panelPath = RoundedPath $panelX $panelY $panelW $panelH 24
            $graphics.FillPath($panelBrush, $panelPath)
            if ($i -ne 0) {
                $outlinePen = [System.Drawing.Pen]::new((HexColor $design.outline 145), 3)
                $graphics.DrawPath($outlinePen, $panelPath)
                $outlinePen.Dispose()
            }
            $panelPath.Dispose()
        } else {
            $graphics.FillRectangle($panelBrush, $panelX, $panelY, $panelW, $panelH)
        }
        $panelBrush.Dispose()

        $labelHex = if ($i -eq 0) { '#fffdf7' } else { $design.label }
        $subHex = if ($i -eq 0) { '#fff7e8' } else { $design.sub }
        DrawCenteredText $graphics $items[$i].label $fontBold $items[$i].size $labelHex `
            ($x0 + 35) ($y0 + 505) ($cellW - 70) 118
        DrawMarker $graphics ($x0 + 75) ($x0 + $cellW - 75) ($y0 + 635) `
            $(if ($i -eq 0) { '#ffe38a' } else { $design.marker })
        DrawDots $graphics ($x0 + 80) ($x0 + $cellW - 88) ($y0 + 661) `
            $(if ($i -eq 0) { '#fff8e8' } else { '#e98510' })
        DrawCenteredText $graphics $items[$i].sub $fontRegular 54 $subHex `
            ($x0 + 35) ($y0 + 684) ($cellW - 70) 85
    }

    # Reassert the exact LINE tap-area boundaries after all resampling and painting.
    $dividerPen = [System.Drawing.Pen]::new((HexColor $design.divider 235), 4)
    $graphics.DrawLine($dividerPen, 833, 0, 833, $H)
    $graphics.DrawLine($dividerPen, 1666, 0, 1666, $H)
    $graphics.DrawLine($dividerPen, 0, 843, $W, 843)
    $dividerPen.Dispose()
    $graphics.Dispose()

    $uncompressedPath = Join-Path $workDir "parent-$($design.name)-full.png"
    $bitmap.Save($uncompressedPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()

    $finalPath = Join-Path $richmenuDir "parent-$($design.name).png"
    $paletteFilter = "[0:v]split[a][b];[a]palettegen=max_colors=$($design.colors):stats_mode=full[p];[b][p]paletteuse=dither=bayer:bayer_scale=3"
    & ffmpeg -hide_banner -loglevel error -y -i $uncompressedPath `
        -filter_complex $paletteFilter -frames:v 1 -compression_level 9 -pred mixed $finalPath
    if ($LASTEXITCODE -ne 0) {
        throw "ffmpeg PNG optimization failed for $finalPath"
    }

    $previewPath = Join-Path $workDir "parent-$($design.name)-350.png"
    & ffmpeg -hide_banner -loglevel error -y -i $finalPath `
        -vf 'scale=350:-1:flags=lanczos' -frames:v 1 $previewPath
    if ($LASTEXITCODE -ne 0) {
        throw "ffmpeg preview generation failed for $previewPath"
    }
}

Get-Item (Join-Path $richmenuDir 'parent-a.png'), (Join-Path $richmenuDir 'parent-b.png') |
    Select-Object Name, Length
