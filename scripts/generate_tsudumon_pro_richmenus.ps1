Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'
$richmenuDir = Join-Path $PSScriptRoot '..\richmenu'
$workDir = Join-Path $richmenuDir '.pro-work'
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

$W = 2500
$H = 1686
$X = @(0, 833, 1666, 2500)
$Y = @(0, 843, 1686)
$fontRegular = 'C:\Windows\Fonts\BIZ-UDGothicR.ttc'
$fontBold = 'C:\Windows\Fonts\BIZ-UDGothicB.ttc'

function HexColor([string]$hex, [int]$alpha = 255) {
    $opaque = [System.Drawing.ColorTranslator]::FromHtml($hex)
    return [System.Drawing.Color]::FromArgb($alpha, $opaque.R, $opaque.G, $opaque.B)
}

function Rect([float]$x, [float]$y, [float]$w, [float]$h) {
    return [System.Drawing.RectangleF]::new($x, $y, $w, $h)
}

function U([string]$base64) {
    return [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($base64))
}

function RoundedPath([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $d = 2 * $r
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

function DrawCenteredText(
    $graphics,
    [string]$text,
    [string]$fontFile,
    [float]$size,
    [string]$hex,
    [float]$x,
    [float]$y,
    [float]$w,
    [float]$h
) {
    $fonts = [System.Drawing.Text.PrivateFontCollection]::new()
    $fonts.AddFontFile($fontFile)
    $font = [System.Drawing.Font]::new(
        $fonts.Families[0],
        $size,
        [System.Drawing.FontStyle]::Regular,
        [System.Drawing.GraphicsUnit]::Pixel
    )
    $brush = [System.Drawing.SolidBrush]::new((HexColor $hex))
    $format = [System.Drawing.StringFormat]::new()
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $format.FormatFlags = [System.Drawing.StringFormatFlags]::NoWrap
    $format.Trimming = [System.Drawing.StringTrimming]::None
    $graphics.DrawString($text, $font, $brush, (Rect $x $y $w $h), $format)
    $format.Dispose()
    $brush.Dispose()
    $font.Dispose()
    $fonts.Dispose()
}

$items = @(
    @{ label = (U '5pWZ5p2Q44KS44Gy44KJ44GP');             sub = (U '44Gk44Gl44GN44GL44KJ77yP5YWoMTnljZjlhYM='); labelSize = 88 },
    @{ label = (U '44OG44K544OI44Gu5LqI5a6a');             sub = (U '56+E5Zuy44KS55u46KuH44GX44Gm55m76Yyy');     labelSize = 84 },
    @{ label = (U '44G+44Gh44GM44GI44KS5b6p57+S');         sub = (U '44OL44Ks44OG44Gg44GR6Kej44GN55u044GZ');     labelSize = 82 },
    @{ label = (U 'M+aXpemWk+eEoeaWmeOBp+OBn+OCgeOBmQ=='); sub = (U '44G+44Ga44Gv44GK44Gf44KB44GX');             labelSize = 78 },
    @{ label = (U '5bGK44GP5puc5pel44O75pmC6ZaT');         sub = (U '44GK55+l44KJ44Gb44Gu6Kit5a6a');             labelSize = 82 },
    @{ label = (U '44GK5pSv5omV44GE44O76Kej57SE');         sub = (U '44GU5Yip55So54q25rOB44Gu56K66KqN');         labelSize = 82 }
)

$designs = @(
    @{
        name = 'a'
        source = 'pro-a-visual.png'
        panel = '#fff8e8'
        panelAlpha = 226
        outline = '#9a5a22'
        heroPanel = '#7c2d12'
        heroAlpha = 226
        label = '#54250f'
        sub = '#7c2d12'
        heroLabel = '#fffdf6'
        heroSub = '#fde8bd'
        divider = '#8f5728'
        colors = 24
    },
    @{
        name = 'b'
        source = 'pro-b-visual.png'
        panel = '#fffdf6'
        panelAlpha = 235
        outline = '#d8ad63'
        heroPanel = '#fff3d4'
        heroAlpha = 239
        label = '#54250f'
        sub = '#7c2d12'
        heroLabel = '#54250f'
        heroSub = '#7c2d12'
        divider = '#d7bc8e'
        colors = 28
    },
    @{
        name = 'c'
        source = 'pro-c-visual.png'
        panel = '#fffaf0'
        panelAlpha = 232
        outline = '#e2a13a'
        heroPanel = '#d97706'
        heroAlpha = 235
        label = '#642b16'
        sub = '#7c2d12'
        heroLabel = '#fffdf6'
        heroSub = '#fff1cd'
        divider = '#d97706'
        colors = 28
    }
)

foreach ($design in $designs) {
    $sourcePath = Join-Path $richmenuDir $design.source
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        throw "Missing generated visual: $sourcePath"
    }

    $source = [System.Drawing.Image]::FromFile($sourcePath)
    $bitmap = [System.Drawing.Bitmap]::new($W, $H, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $graphics.DrawImage($source, 0, 0, $W, $H)
    $source.Dispose()

    for ($i = 0; $i -lt 6; $i++) {
        $row = [int][Math]::Floor($i / 3.0)
        $col = $i % 3
        $x0 = $X[$col]
        $y0 = $Y[$row]
        $cellW = $X[$col + 1] - $x0

        $panelPath = RoundedPath ($x0 + 38) ($y0 + 548) ($cellW - 76) 242 30
        $panelHex = if ($i -eq 0) { $design.heroPanel } else { $design.panel }
        $panelAlpha = if ($i -eq 0) { $design.heroAlpha } else { $design.panelAlpha }
        $panelBrush = [System.Drawing.SolidBrush]::new((HexColor $panelHex $panelAlpha))
        $outlinePen = [System.Drawing.Pen]::new((HexColor $design.outline 205), $(if ($i -eq 0) { 6 } else { 4 }))
        $graphics.FillPath($panelBrush, $panelPath)
        $graphics.DrawPath($outlinePen, $panelPath)
        $panelBrush.Dispose()
        $outlinePen.Dispose()
        $panelPath.Dispose()

        $labelHex = if ($i -eq 0) { $design.heroLabel } else { $design.label }
        $subHex = if ($i -eq 0) { $design.heroSub } else { $design.sub }
        DrawCenteredText $graphics $items[$i].label $fontBold $items[$i].labelSize $labelHex ($x0 + 42) ($y0 + 566) ($cellW - 84) 104
        DrawCenteredText $graphics $items[$i].sub $fontRegular 48 $subHex ($x0 + 42) ($y0 + 688) ($cellW - 84) 66
    }

    # Reassert the exact LINE tap-area boundaries after resampling the generated art.
    $dividerPen = [System.Drawing.Pen]::new((HexColor $design.divider 218), 4)
    $graphics.DrawLine($dividerPen, 833, 0, 833, $H)
    $graphics.DrawLine($dividerPen, 1666, 0, 1666, $H)
    $graphics.DrawLine($dividerPen, 0, 843, $W, 843)
    $dividerPen.Dispose()

    $graphics.Dispose()
    $uncompressedPath = Join-Path $workDir "pro-$($design.name)-full.png"
    $bitmap.Save($uncompressedPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()

    $finalPath = Join-Path $richmenuDir "pro-$($design.name).png"
    $paletteFilter = "[0:v]split[a][b];[a]palettegen=max_colors=$($design.colors):stats_mode=full[p];[b][p]paletteuse=dither=bayer:bayer_scale=3"
    & ffmpeg -hide_banner -loglevel error -y -i $uncompressedPath `
        -filter_complex $paletteFilter `
        -frames:v 1 -compression_level 9 -pred mixed $finalPath
    if ($LASTEXITCODE -ne 0) {
        throw "ffmpeg PNG optimization failed for $finalPath"
    }
}

Get-ChildItem $richmenuDir -Filter 'pro-?.png' | Select-Object Name, Length
