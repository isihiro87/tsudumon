Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'
$outDir = Join-Path $PSScriptRoot '..\richmenu'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$W = 2500
$H = 1686
$X = @(0, 833, 1666, 2500)
$Y = @(0, 843, 1686)
$fontRegular = 'C:\Windows\Fonts\BIZ-UDGothicR.ttc'
$fontBold = 'C:\Windows\Fonts\BIZ-UDGothicB.ttc'

function Color([string]$hex) {
    return [System.Drawing.ColorTranslator]::FromHtml($hex)
}

function U([string]$base64) {
    return [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($base64))
}

function Rect([int]$x, [int]$y, [int]$w, [int]$h) {
    return [System.Drawing.RectangleF]::new($x, $y, $w, $h)
}

function RoundedPath([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
    $p = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $d = 2 * $r
    $p.AddArc($x, $y, $d, $d, 180, 90)
    $p.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $p.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $p.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $p.CloseFigure()
    return $p
}

function MakePen([string]$hex, [float]$width) {
    $p = [System.Drawing.Pen]::new((Color $hex), $width)
    $p.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $p.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $p.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    return $p
}

function DrawCenteredText($g, [string]$text, [string]$fontFile, [float]$size, [string]$hex, [float]$x, [float]$y, [float]$w, [float]$h) {
    $fc = [System.Drawing.Text.PrivateFontCollection]::new()
    $fc.AddFontFile($fontFile)
    $font = [System.Drawing.Font]::new($fc.Families[0], $size, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
    $brush = [System.Drawing.SolidBrush]::new((Color $hex))
    $fmt = [System.Drawing.StringFormat]::new()
    $fmt.Alignment = [System.Drawing.StringAlignment]::Center
    $fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
    $fmt.FormatFlags = [System.Drawing.StringFormatFlags]::NoWrap
    $g.DrawString($text, $font, $brush, (Rect $x $y $w $h), $fmt)
    $fmt.Dispose(); $brush.Dispose(); $font.Dispose(); $fc.Dispose()
}

function DrawIcon($g, [string]$kind, [float]$cx, [float]$cy, [string]$hex, [float]$scale = 1.0, [bool]$filled = $false) {
    $s = $scale
    $pen = MakePen $hex (18 * $s)
    $thin = MakePen $hex (12 * $s)
    $brush = [System.Drawing.SolidBrush]::new((Color $hex))
    switch ($kind) {
        'book' {
            $p1 = [System.Drawing.PointF[]]@(
                [System.Drawing.PointF]::new($cx-105*$s,$cy-70*$s), [System.Drawing.PointF]::new($cx-28*$s,$cy-54*$s),
                [System.Drawing.PointF]::new($cx,$cy-25*$s), [System.Drawing.PointF]::new($cx,$cy+85*$s),
                [System.Drawing.PointF]::new($cx-28*$s,$cy+60*$s), [System.Drawing.PointF]::new($cx-105*$s,$cy+45*$s)
            )
            $p2 = [System.Drawing.PointF[]]@(
                [System.Drawing.PointF]::new($cx+105*$s,$cy-70*$s), [System.Drawing.PointF]::new($cx+28*$s,$cy-54*$s),
                [System.Drawing.PointF]::new($cx,$cy-25*$s), [System.Drawing.PointF]::new($cx,$cy+85*$s),
                [System.Drawing.PointF]::new($cx+28*$s,$cy+60*$s), [System.Drawing.PointF]::new($cx+105*$s,$cy+45*$s)
            )
            $g.DrawPolygon($pen,$p1); $g.DrawPolygon($pen,$p2)
            $g.DrawLine($thin,$cx-76*$s,$cy-30*$s,$cx-27*$s,$cy-20*$s)
            $g.DrawLine($thin,$cx+76*$s,$cy-30*$s,$cx+27*$s,$cy-20*$s)
        }
        'calendar' {
            $g.DrawRectangle($pen,$cx-94*$s,$cy-72*$s,188*$s,155*$s)
            $g.DrawLine($pen,$cx-94*$s,$cy-25*$s,$cx+94*$s,$cy-25*$s)
            $g.DrawLine($pen,$cx-52*$s,$cy-91*$s,$cx-52*$s,$cy-55*$s)
            $g.DrawLine($pen,$cx+52*$s,$cy-91*$s,$cx+52*$s,$cy-55*$s)
            foreach($dx in @(-50,0,50)){ foreach($dy in @(12,52)){ $g.FillEllipse($brush,$cx+$dx*$s-7*$s,$cy+$dy*$s-7*$s,14*$s,14*$s) } }
        }
        'retry' {
            $g.DrawArc($pen,$cx-91*$s,$cy-83*$s,182*$s,166*$s,28,278)
            $pts = [System.Drawing.PointF[]]@(
                [System.Drawing.PointF]::new($cx+80*$s,$cy-72*$s),
                [System.Drawing.PointF]::new($cx+100*$s,$cy-12*$s),
                [System.Drawing.PointF]::new($cx+39*$s,$cy-24*$s)
            )
            $g.FillPolygon($brush,$pts)
            $g.DrawLine($thin,$cx-38*$s,$cy+8*$s,$cx-5*$s,$cy+40*$s)
            $g.DrawLine($thin,$cx-5*$s,$cy+40*$s,$cx+55*$s,$cy-27*$s)
        }
        'gift' {
            $g.DrawRectangle($pen,$cx-96*$s,$cy-27*$s,192*$s,110*$s)
            $g.DrawRectangle($pen,$cx-108*$s,$cy-58*$s,216*$s,36*$s)
            $g.DrawLine($pen,$cx,$cy-58*$s,$cx,$cy+83*$s)
            $g.DrawArc($pen,$cx-82*$s,$cy-103*$s,82*$s,58*$s,195,160)
            $g.DrawArc($pen,$cx,$cy-103*$s,82*$s,58*$s,185,160)
        }
        'graph' {
            $g.DrawLine($pen,$cx-104*$s,$cy+80*$s,$cx+104*$s,$cy+80*$s)
            $g.DrawLine($pen,$cx-104*$s,$cy+80*$s,$cx-104*$s,$cy-80*$s)
            $pts = [System.Drawing.PointF[]]@(
                [System.Drawing.PointF]::new($cx-79*$s,$cy+43*$s),
                [System.Drawing.PointF]::new($cx-27*$s,$cy-2*$s),
                [System.Drawing.PointF]::new($cx+17*$s,$cy+20*$s),
                [System.Drawing.PointF]::new($cx+83*$s,$cy-59*$s)
            )
            $g.DrawLines($pen,$pts)
            foreach($pt in $pts){ $g.FillEllipse($brush,$pt.X-10*$s,$pt.Y-10*$s,20*$s,20*$s) }
        }
        'clock' {
            $g.DrawEllipse($pen,$cx-88*$s,$cy-88*$s,176*$s,176*$s)
            $g.DrawLine($pen,$cx,$cy,$cx,$cy-53*$s)
            $g.DrawLine($pen,$cx,$cy,$cx+48*$s,$cy+30*$s)
            $g.FillEllipse($brush,$cx-10*$s,$cy-10*$s,20*$s,20*$s)
        }
        'gear' {
            $g.DrawEllipse($pen,$cx-70*$s,$cy-70*$s,140*$s,140*$s)
            $g.DrawEllipse($pen,$cx-22*$s,$cy-22*$s,44*$s,44*$s)
            for($i=0;$i -lt 8;$i++){
                $a = $i * [Math]::PI / 4
                $x1=$cx+[Math]::Cos($a)*72*$s; $y1=$cy+[Math]::Sin($a)*72*$s
                $x2=$cx+[Math]::Cos($a)*103*$s; $y2=$cy+[Math]::Sin($a)*103*$s
                $g.DrawLine($pen,$x1,$y1,$x2,$y2)
            }
        }
    }
    $brush.Dispose(); $thin.Dispose(); $pen.Dispose()
}

$items = @(
    @{ icon='book';     label=(U '5pWZ5p2Q44KS44Gy44KJ44GP');             sub=(U '44Gk44Gl44GN44GL44KJ77yP5YWoMTnljZjlhYM=') },
    @{ icon='calendar'; label=(U '44OG44K544OI44Gu5LqI5a6a');             sub=(U '56+E5Zuy44KS55u46KuH44GX44Gm55m76Yyy') },
    @{ icon='retry';    label=(U '44G+44Gh44GM44GI44KS5b6p57+S');         sub=(U '44OL44Ks44OG44Gg44GR6Kej44GN55u044GZ') },
    @{ icon='gift';     label=(U 'M+aXpemWk+eEoeaWmeOBp+OBn+OCgeOBmQ=='); sub=(U '44G+44Ga44Gv44GK44Gf44KB44GX') },
    @{ icon='clock';    label=(U '5bGK44GP5puc5pel44O75pmC6ZaT');         sub=(U '44GK55+l44KJ44Gb44Gu6Kit5a6a') },
    @{ icon='gear';     label=(U '44GK5pSv5omV44GE44O76Kej57SE');         sub=(U '44GU5Yip55So54q25rOB44Gu56K66KqN') }
)

function DrawMenu([string]$design, [string]$variant, [string]$path) {
    $bmp = [System.Drawing.Bitmap]::new($W,$H,[System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

    if($variant -eq 'record'){
        $items[3] = @{ icon='graph'; label=(U '5a2m57+S44Gu6KiY6Yyy'); sub=(U '44GM44KT44Gw44KK44KS6KaL44KL') }
    } else {
        $items[3] = @{ icon='gift'; label=(U 'M+aXpemWk+eEoeaWmeOBp+OBn+OCgeOBmQ=='); sub=(U '44G+44Ga44Gv44GK44Gf44KB44GX') }
    }

    if($design -eq 'a'){
        # Design A: parchment / antique-map palette. Notebook rules belong to B only.
        $g.Clear((Color '#f6e7c4'))
        $mapWash = [System.Drawing.SolidBrush]::new((Color '#edd39c'))
        $g.FillEllipse($mapWash,-210,-250,940,670)
        $g.FillEllipse($mapWash,1880,1130,850,720)
        $mapWash.Dispose()
        $mapPen = [System.Drawing.Pen]::new((Color '#d6ae68'),4)
        $mapPen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dot
        $g.DrawArc($mapPen,70,85,510,430,202,118)
        $g.DrawArc($mapPen,1980,1165,440,350,18,137)
        $mapPen.Dispose()
        for($i=0;$i -lt 6;$i++){
            $r=[int][Math]::Floor($i/3.0); $c=$i%3
            $x0=$X[$c]; $y0=$Y[$r]; $cw=$X[$c+1]-$x0; $ch=$Y[$r+1]-$y0
            $pathCard=RoundedPath ($x0+22) ($y0+22) ($cw-44) ($ch-44) 30
            $fill=[System.Drawing.SolidBrush]::new((Color $(if($i -eq 0){'#d99a32'}else{'#f9edcf'})))
            $line=[System.Drawing.Pen]::new((Color $(if($i -eq 0){'#7a3517'}else{'#b7792b'})),5)
            $g.FillPath($fill,$pathCard); $g.DrawPath($line,$pathCard)
            $fill.Dispose(); $line.Dispose(); $pathCard.Dispose()
            $iconColor=if($i -eq 0){'#fff8e8'}else{'#6b2c16'}
            DrawIcon $g $items[$i].icon ($x0+$cw/2) ($y0+225) $iconColor $(if($i -eq 0){1.12}else{1.0})
            $labelColor=if($i -eq 0){'#fff8e8'}else{'#54250f'}
            $subColor=if($i -eq 0){'#fff2d2'}else{'#7c2d12'}
            DrawCenteredText $g $items[$i].label $fontBold 82 $labelColor ($x0+24) ($y0+383) ($cw-48) 118
            DrawCenteredText $g $items[$i].sub $fontRegular 48 $subColor ($x0+24) ($y0+532) ($cw-48) 80
            $orn=MakePen $(if($i -eq 0){'#ffe1a1'}else{'#c58b3a'}) 5
            $g.DrawLine($orn,$x0+$cw/2-70,$y0+655,$x0+$cw/2+70,$y0+655)
            $orn.Dispose()
        }
        $grid=[System.Drawing.Pen]::new((Color '#9d6329'),3)
        $g.DrawLine($grid,833,0,833,$H); $g.DrawLine($grid,1666,0,1666,$H); $g.DrawLine($grid,0,843,$W,843)
        $grid.Dispose()
    }
    elseif($design -eq 'b'){
        $g.Clear((Color '#fffdf8'))
        $rule=[System.Drawing.Pen]::new((Color '#eee5d7'),2)
        for($yy=46;$yy -lt $H;$yy+=54){ $g.DrawLine($rule,0,$yy,$W,$yy) }
        $rule.Dispose()
        $fills=@('#f8d991','#fce9b8','#f7e0ad','#eee6d8','#f3eadf','#e9dfd2')
        for($i=0;$i -lt 6;$i++){
            $r=[int][Math]::Floor($i/3.0); $c=$i%3
            $x0=$X[$c]; $y0=$Y[$r]; $cw=$X[$c+1]-$x0
            $pad=if($i -eq 0){18}else{31}
            $p=RoundedPath ($x0+$pad) ($y0+45) ($cw-2*$pad) 750 22
            $fill=[System.Drawing.SolidBrush]::new((Color $fills[$i]))
            $outline=[System.Drawing.Pen]::new((Color '#ddcfba'),4)
            $g.FillPath($fill,$p); $g.DrawPath($outline,$p)
            $fill.Dispose(); $outline.Dispose(); $p.Dispose()
            $tape=[System.Drawing.SolidBrush]::new((Color '#f1c978'))
            $g.FillRectangle($tape,$x0+$cw/2-75,$y0+32,150,40); $tape.Dispose()
            DrawIcon $g $items[$i].icon ($x0+$cw/2) ($y0+235) '#7c2d12' $(if($i -eq 0){1.10}else{0.98})
            DrawCenteredText $g $items[$i].label $fontBold $(if($i -eq 0){86}else{82}) '#54250f' ($x0+18) ($y0+390) ($cw-36) 120
            DrawCenteredText $g $items[$i].sub $fontRegular 50 '#6f4630' ($x0+20) ($y0+540) ($cw-40) 82
        }
        $grid=[System.Drawing.Pen]::new((Color '#d8cbbb'),3)
        $g.DrawLine($grid,833,0,833,$H); $g.DrawLine($grid,1666,0,1666,$H); $g.DrawLine($grid,0,843,$W,843)
        $grid.Dispose()
    }
    else {
        $g.Clear((Color '#fffdf8'))
        $fills=@('#f59e0b','#fde68a','#fcd9a0','#fbbf24','#f5ead6','#efe3cf')
        for($i=0;$i -lt 6;$i++){
            $r=[int][Math]::Floor($i/3.0); $c=$i%3
            $x0=$X[$c]; $y0=$Y[$r]; $cw=$X[$c+1]-$x0
            $p=RoundedPath ($x0+4) ($y0+4) ($cw-8) 835 16
            $fill=[System.Drawing.SolidBrush]::new((Color $fills[$i]))
            $g.FillPath($fill,$p); $fill.Dispose(); $p.Dispose()
            $dark = if($i -eq 0){'#ffffff'}else{'#642b16'}
            if($i -eq 0){
                $circleFill=[System.Drawing.SolidBrush]::new((Color '#ffffff'))
                $g.FillEllipse($circleFill,$x0+$cw/2-125,$y0+82,250,250); $circleFill.Dispose()
                DrawIcon $g $items[$i].icon ($x0+$cw/2) ($y0+205) '#d97706' 0.92
            } else {
                $circleFill=[System.Drawing.SolidBrush]::new((Color '#fffaf0'))
                $g.FillEllipse($circleFill,$x0+$cw/2-118,$y0+89,236,236); $circleFill.Dispose()
                DrawIcon $g $items[$i].icon ($x0+$cw/2) ($y0+207) '#7c2d12' 0.86
            }
            DrawCenteredText $g $items[$i].label $fontBold $(if($i -eq 0){86}else{82}) $dark ($x0+18) ($y0+400) ($cw-36) 120
            DrawCenteredText $g $items[$i].sub $fontRegular 50 $dark ($x0+18) ($y0+550) ($cw-36) 80
            $dotBrush=[System.Drawing.SolidBrush]::new((Color $dark))
            foreach($dx in @(-24,0,24)){ $g.FillEllipse($dotBrush,$x0+$cw/2+$dx-4,$y0+687,8,8) }
            $dotBrush.Dispose()
        }
    }

    $g.Dispose()
    $bmp.Save($path,[System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

foreach($design in @('a','b','c')){
    foreach($variant in @('trial','record')){
        $file = Join-Path $outDir "tsudumon-menu-$design-$variant.png"
        DrawMenu $design $variant $file
    }
}

Get-ChildItem $outDir -Filter 'tsudumon-menu-*.png' | Select-Object Name,Length
