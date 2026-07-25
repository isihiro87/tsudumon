param(
  [string]$Root = $(if ($PSScriptRoot) { (Resolve-Path (Join-Path $PSScriptRoot '..')).Path } else { (Get-Location).Path })
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$referenceDir = Join-Path $Root 'reference'
$htmlDir = Join-Path $Root 'covers\html\topics'
$outDir = Join-Path $Root 'covers\out\topics'
$tmpDir = Join-Path $Root 'tmp\topic-cover-images'
New-Item -ItemType Directory -Force -Path $htmlDir, $outDir, $tmpDir | Out-Null

function Plain([string]$s) {
  if ($null -eq $s) { return '' }
  return ($s -replace '\*\*(.*?)\*\*', '$1')
}

function ColorArgb([int]$a, [string]$hex) {
  $hex = $hex.TrimStart('#')
  return [System.Drawing.Color]::FromArgb($a, [Convert]::ToInt32($hex.Substring(0,2),16), [Convert]::ToInt32($hex.Substring(2,2),16), [Convert]::ToInt32($hex.Substring(4,2),16))
}

function RoundedRect([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
  $p = New-Object System.Drawing.Drawing2D.GraphicsPath
  $d = $r * 2
  $p.AddArc($x, $y, $d, $d, 180, 90)
  $p.AddArc(($x + $w - $d), $y, $d, $d, 270, 90)
  $p.AddArc(($x + $w - $d), ($y + $h - $d), $d, $d, 0, 90)
  $p.AddArc($x, ($y + $h - $d), $d, $d, 90, 90)
  $p.CloseFigure()
  return $p
}

function Draw-RoundedRect($g, $brush, $pen, [float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
  $path = RoundedRect $x $y $w $h $r
  if ($brush) { $g.FillPath($brush, $path) }
  if ($pen) { $g.DrawPath($pen, $path) }
  $path.Dispose()
}

function Draw-CoverImage($g, $img, [float]$x, [float]$y, [float]$w, [float]$h) {
  $scale = [Math]::Max($w / $img.Width, $h / $img.Height)
  $sw = $w / $scale
  $sh = $h / $scale
  $sx = ($img.Width - $sw) / 2
  $sy = ($img.Height - $sh) / 2
  $dest = New-Object System.Drawing.RectangleF($x, $y, $w, $h)
  $src = New-Object System.Drawing.RectangleF($sx, $sy, $sw, $sh)
  $g.DrawImage($img, $dest, $src, [System.Drawing.GraphicsUnit]::Pixel)
}

function Draw-CenteredText($g, [string]$text, $font, $brush, [float]$x, [float]$y, [float]$w, [float]$h) {
  $fmt = New-Object System.Drawing.StringFormat
  $fmt.Alignment = [System.Drawing.StringAlignment]::Center
  $fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
  $g.DrawString($text, $font, $brush, (New-Object System.Drawing.RectangleF($x,$y,$w,$h)), $fmt)
  $fmt.Dispose()
}

function Save-PdfFromBitmap($bitmap, [string]$pdfPath) {
  $ms = New-Object System.IO.MemoryStream
  $codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' } | Select-Object -First 1
  $params = New-Object System.Drawing.Imaging.EncoderParameters(1)
  $params.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality, 92L)
  $bitmap.Save($ms, $codec, $params)
  $jpg = $ms.ToArray()
  $content = "q`n595.28 0 0 841.89 0 0 cm`n/Im0 Do`nQ`n"
  $objects = @(
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /XObject /Subtype /Image /Width 1240 /Height 1754 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length $($jpg.Length) >>`nstream`n__JPEG__`nendstream",
    "<< /Length $($content.Length) >>`nstream`n$content`nendstream"
  )
  $fs = [System.IO.File]::Create($pdfPath)
  $enc = [System.Text.Encoding]::ASCII
  $offsets = New-Object System.Collections.Generic.List[int]
  $writeText = { param($s) $b=$enc.GetBytes($s); $fs.Write($b,0,$b.Length) }
  & $writeText "%PDF-1.4`n"
  for ($i=0; $i -lt $objects.Count; $i++) {
    $offsets.Add([int]$fs.Position)
    & $writeText "$($i+1) 0 obj`n"
    if ($objects[$i].Contains('__JPEG__')) {
      $parts = $objects[$i].Split('__JPEG__')
      & $writeText $parts[0]
      $fs.Write($jpg,0,$jpg.Length)
      & $writeText $parts[1]
    } else {
      & $writeText $objects[$i]
    }
    & $writeText "`nendobj`n"
  }
  $xref = $fs.Position
  & $writeText "xref`n0 6`n0000000000 65535 f `n"
  foreach ($o in $offsets) { & $writeText ("{0:0000000000} 00000 n `n" -f $o) }
  & $writeText "trailer << /Size 6 /Root 1 0 R >>`nstartxref`n$xref`n%%EOF`n"
  $fs.Dispose()
  $ms.Dispose()
  $params.Dispose()
}

function Get-PngForWebp([string]$imageName) {
  $src = Join-Path $Root "assets\reference\$imageName"
  $dst = Join-Path $tmpDir ([IO.Path]::GetFileNameWithoutExtension($imageName) + '.png')
  if (!(Test-Path $dst)) {
    & ffmpeg -y -v error -i $src $dst
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed: $src" }
  }
  return $dst
}

function Draw-TopicCover($data, $topic, [int]$topicNo, [string]$pngPath, [string]$pdfPath) {
  $bmp = New-Object System.Drawing.Bitmap(1240, 1754, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $g.Clear([System.Drawing.Color]::FromArgb(253,248,240))

  $cream = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255,250,241))
  $orange = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(180,83,9))
  $dark = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(44,37,32))
  $muted = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(124,113,106))
  $brown = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(91,68,53))
  $white = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
  $paperBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(210,255,255,255))
  $borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(180,83,9), 4)

  Draw-RoundedRect $g $paperBrush $borderPen 104 96 1032 1562 24
  foreach ($d in @(@(220,280,7,70),@(330,390,5,60),@(970,330,6,80),@(905,1120,5,55),@(270,1320,4,60))) {
    $b = New-Object System.Drawing.SolidBrush((ColorArgb $d[3] '#d97706'))
    $g.FillEllipse($b, $d[0], $d[1], $d[2]*2, $d[2]*2)
    $b.Dispose()
  }

  $bigFont = New-Object System.Drawing.Font('Yu Gothic', 420, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  $bigBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(20,180,83,9))
  $g.DrawString([string]$topicNo, $bigFont, $bigBrush, 800, 105)

  Draw-RoundedRect $g $orange $null 168 172 174 84 18
  $badgeFont = New-Object System.Drawing.Font('Yu Gothic', 36, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  Draw-CenteredText $g $data.volume $badgeFont $white 168 172 174 84

  $title = Plain $topic.name
  $titleSize = if ($title.Length -ge 15) { 50 } else { 58 }
  $titleFont = New-Object System.Drawing.Font('Yu Gothic', $titleSize, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  $rangeFont = New-Object System.Drawing.Font('Yu Gothic', 27, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  $fmt = New-Object System.Drawing.StringFormat
  $fmt.Alignment = [System.Drawing.StringAlignment]::Near
  $g.DrawString($title, $titleFont, $dark, (New-Object System.Drawing.RectangleF(370,160,690,145)), $fmt)
  $g.DrawString("$($data.title)／単元$topicNo", $rangeFont, $muted, 372, 290)

  $imgPath = Get-PngForWebp $topic.image
  $img = [System.Drawing.Image]::FromFile($imgPath)
  $state = $g.Save()
  $cx = 620; $cy = 608
  $g.TranslateTransform($cx, $cy)
  $angle = if ($topicNo % 2 -eq 0) { 2 } else { -2 }
  $g.RotateTransform($angle)
  $g.TranslateTransform((-455), (-277))
  Draw-RoundedRect $g $cream (New-Object System.Drawing.Pen((ColorArgb 100 '#b45309'),4)) 0 0 910 555 26
  $tape = New-Object System.Drawing.SolidBrush((ColorArgb 95 '#d97706'))
  Draw-RoundedRect $g $tape $null 76 -28 190 58 8
  Draw-RoundedRect $g $tape $null 648 -28 190 58 8
  Draw-CoverImage $g $img 26 26 858 503
  $g.Restore($state)
  $img.Dispose()

  Draw-RoundedRect $g (New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(235,255,255,255))) (New-Object System.Drawing.Pen((ColorArgb 115 '#b45309'),4)) 164 1020 738 292 26
  $hFont = New-Object System.Drawing.Font('Yu Gothic', 31, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  $liFont = New-Object System.Drawing.Font('Yu Gothic', 25, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  $noFont = New-Object System.Drawing.Font('Yu Gothic', 24, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  $targetBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(220,38,38))
  $targetPen = New-Object System.Drawing.Pen([System.Drawing.Color]::White, 4)
  $g.FillEllipse($targetBrush, 202, 1050, 30, 30)
  $g.DrawEllipse($targetPen, 207, 1055, 20, 20)
  $g.FillEllipse($white, 214, 1062, 6, 6)
  $g.DrawString('この単元でわかること', $hFont, (New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(124,45,18))), 244, 1044)
  $learn = @()
  if ($topic.learn) { $learn = @($topic.learn) } else { $learn = @($topic.sections | ForEach-Object { $_.heading }) }
  $learn = @($learn | Where-Object { $_ } | Select-Object -First 3 | ForEach-Object { Plain $_ })
  for ($i=0; $i -lt $learn.Count; $i++) {
    $y = 1102 + $i * 67
    if ($i -gt 0) { $g.DrawLine((New-Object System.Drawing.Pen((ColorArgb 55 '#b45309'),2)), 198, ($y - 13), 868, ($y - 13)) }
    $g.FillEllipse($orange, 198, $y, 44, 44)
    Draw-CenteredText $g ([string]($i+1)) $noFont $white 198 $y 44 44
    $g.DrawString($learn[$i], $liFont, $dark, (New-Object System.Drawing.RectangleF(256,($y - 3),600,62)), $fmt)
  }

  Draw-RoundedRect $g $white (New-Object System.Drawing.Pen((ColorArgb 140 '#b45309'),4)) 930 1012 232 108 24
  $speechFont = New-Object System.Drawing.Font('Yu Gothic', 24, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  Draw-CenteredText $g "この単元も`nがんばろう！" $speechFont $brown 930 1012 232 108
  $mascotPath = Join-Path $Root 'assets\characters\manabi_banzai.png'
  if (Test-Path $mascotPath) {
    $mascot = [System.Drawing.Image]::FromFile($mascotPath)
    $g.DrawImage($mascot, 950, 1148, 188, [int](188 * $mascot.Height / $mascot.Width))
    $mascot.Dispose()
  }

  $footer = New-Object System.Drawing.Drawing2D.GraphicsPath
  $pts = @(
    [System.Drawing.PointF]::new(104,1470),[System.Drawing.PointF]::new(187,1457),[System.Drawing.PointF]::new(280,1468),
    [System.Drawing.PointF]::new(372,1450),[System.Drawing.PointF]::new(476,1465),[System.Drawing.PointF]::new(600,1447),
    [System.Drawing.PointF]::new(703,1461),[System.Drawing.PointF]::new(826,1450),[System.Drawing.PointF]::new(951,1465),
    [System.Drawing.PointF]::new(1054,1457),[System.Drawing.PointF]::new(1136,1470),[System.Drawing.PointF]::new(1136,1658),
    [System.Drawing.PointF]::new(104,1658)
  )
  $footer.AddPolygon($pts)
  $g.FillPath($orange, $footer)
  $footerFont = New-Object System.Drawing.Font('Yu Gothic', 31, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  Draw-CenteredText $g 'つづもん 中学歴史 まとめて復習ワーク' $footerFont $white 104 1515 1032 120

  $bmp.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
  Save-PdfFromBitmap $bmp $pdfPath
  $g.Dispose()
  $bmp.Dispose()
}

$count = 0
Get-ChildItem $referenceDir -Filter '*.json' | Sort-Object Name | ForEach-Object {
  $chapterNo = $_.Name.Substring(0,2)
  $data = Get-Content -Raw -Encoding UTF8 $_.FullName | ConvertFrom-Json
  for ($i=0; $i -lt $data.topics.Count; $i++) {
    $topic = $data.topics[$i]
    $stem = "$chapterNo-$($topic.topicId)"
    Draw-TopicCover $data $topic ($i+1) (Join-Path $outDir "$stem.png") (Join-Path $outDir "$stem.pdf")
    $count++
    if ($count % 10 -eq 0) { Write-Host "rendered $count" }
  }
}
Write-Host "generated $count topic covers"
