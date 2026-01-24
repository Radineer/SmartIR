# イリス 画像生成プロンプト集

## 必要な画像一覧

| No | 画像 | 用途 | サイズ |
|----|------|------|--------|
| 1 | 立ち絵（通常） | トップページ、メイン | 1024x1536 |
| 2 | 立ち絵（分析モード） | 分析結果表示 | 1024x1536 |
| 3 | アイコン | ヘッダー、favicon | 512x512 |
| 4 | OGP用 | SNSシェア | 1200x630 |
| 5 | 表情差分セット | 各種UI | 512x512 x 6種 |

---

## Midjourney用プロンプト

### 1. 立ち絵（通常）
```
anime girl, silver short bob hair with subtle rainbow shimmer,
bright blue eyes with circuit pattern in right iris,
wearing white futuristic lab coat with holographic blue trim,
dark navy turtleneck underneath, gentle warm smile,
small holographic display floating near her hand,
clean white background, full body shot, standing pose,
soft professional lighting, high quality anime illustration,
modern anime style, detailed, vibrant colors --ar 2:3 --v 6
```

### 2. 立ち絵（分析モード）
```
anime girl, silver short bob hair flowing with energy,
glowing bright blue eyes with data streams visible in pupils,
wearing white futuristic lab coat, serious focused expression,
multiple holographic charts and financial graphs floating around her,
blue and cyan ambient lighting, cyberpunk atmosphere,
dark background with data visualization,
full body shot, confident stance,
high quality anime illustration --ar 2:3 --v 6
```

### 3. アイコン
```
anime girl portrait, silver short hair, bright blue eyes with subtle circuit pattern,
white collar visible, gentle friendly smile,
simple gradient background blue to white,
clean modern anime style, suitable for app icon,
centered composition, high quality --ar 1:1 --v 6
```

### 4. OGP/バナー用
```
anime girl, silver hair, blue eyes with circuit pattern,
white lab coat, holding holographic tablet showing stock charts,
"AI-IR Insight" text logo space on left side,
professional financial theme, blue color scheme,
wide banner composition, modern clean design --ar 1200:630 --v 6
```

---

## Stable Diffusion (SDXL) 用プロンプト

### 共通ネガティブプロンプト
```
lowres, bad anatomy, bad hands, text, error, missing fingers,
extra digit, fewer digits, cropped, worst quality, low quality,
normal quality, jpeg artifacts, signature, watermark, username,
blurry, bad feet, poorly drawn face, mutation, deformed
```

### 1. 立ち絵（通常）
```
Prompt:
masterpiece, best quality, 1girl, solo,
silver short bob hair, (rainbow shimmer hair:0.3),
bright blue eyes, (circuit pattern in right eye:0.8),
white futuristic lab coat, holographic blue trim on coat,
dark navy turtleneck, gentle smile,
small holographic display near hand,
clean white background, full body, standing,
anime style, detailed face, soft lighting

Model: animagine-xl-3.1 or pony-diffusion-xl
CFG Scale: 7
Steps: 30
Size: 768x1152
```

### 2. 分析モード
```
Prompt:
masterpiece, best quality, 1girl, solo,
silver short bob hair, (energy flowing through hair:0.5),
(glowing blue eyes:1.2), (data streams in pupils:0.9),
white futuristic lab coat, serious expression, focused,
(holographic charts floating:1.1), financial graphs,
blue cyan ambient lighting, cyberpunk,
dark background, data visualization,
full body, confident stance, anime style

Model: animagine-xl-3.1
CFG Scale: 7
Steps: 35
Size: 768x1152
```

---

## DALL-E 3 用プロンプト

### 1. 立ち絵（通常）
```
Create an anime-style illustration of a young woman with silver
short bob-cut hair that has a subtle rainbow shimmer. She has
bright blue eyes, with her right eye featuring a subtle digital
circuit pattern. She wears a white futuristic lab coat with
glowing blue holographic trim, over a dark navy turtleneck.
She has a gentle, warm smile. A small holographic display floats
near her hand. The background is clean white. Full body shot,
standing in a relaxed pose. Modern anime illustration style,
high quality, professional, soft lighting.
```

### 2. 分析モード
```
Create an anime-style illustration of a young woman with silver
short bob-cut hair that appears to be flowing with energy. Her
eyes are glowing bright blue with visible data streams in her
pupils. She wears a white futuristic lab coat and has a serious,
focused expression. Multiple holographic financial charts and
graphs float around her. The lighting is blue and cyan, creating
a cyberpunk atmosphere. Dark background with data visualization
elements. Full body shot, confident stance.
```

### 3. アイコン
```
Create a simple anime-style portrait icon of a young woman with
silver short hair and bright blue eyes with a subtle circuit
pattern. White collar visible. Gentle, friendly smile. Simple
gradient background from blue to white. Clean modern anime style,
suitable for an app icon. Square format, centered composition.
```

---

## 画像生成後のチェックリスト

- [ ] 右目のサーキットパターンが確認できる
- [ ] 髪色がシルバー/ホワイトになっている
- [ ] ラボコートが未来的なデザイン
- [ ] 表情が設定に合っている
- [ ] 背景が用途に適している
- [ ] 解像度が十分（最低768px以上）

---

## 画像の配置先

生成した画像は以下に配置:

```
/frontend/public/images/iris/
├── iris-normal.png      # 通常立ち絵
├── iris-analysis.png    # 分析モード
├── iris-icon.png        # アイコン
├── iris-ogp.png         # OGP用
└── expressions/         # 表情差分
    ├── smile.png
    ├── surprise.png
    ├── confused.png
    ├── thinking.png
    ├── freeze.png
    └── eating.png
```

---

## 推奨ツール

| ツール | 特徴 | おすすめ度 |
|--------|------|-----------|
| **Midjourney v6** | 高品質、アニメ調も得意 | ★★★★★ |
| **NovelAI** | アニメ特化、一貫性高い | ★★★★★ |
| **Stable Diffusion + LoRA** | カスタマイズ性最高 | ★★★★☆ |
| **DALL-E 3** | 手軽、指示理解力高い | ★★★☆☆ |
| **にじジャーニー** | 日本アニメ調に強い | ★★★★☆ |

### 一貫性を保つコツ
1. 同じツール・設定で全画像を生成
2. シードを固定（可能な場合）
3. 生成後に軽くレタッチで統一感を出す
