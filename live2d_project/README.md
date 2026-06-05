# イリス Live2D化プロジェクト

## 現在の方針（2026-03-20 更新）

**VRM路線を正式採用。** aituber-kit + VRMモデル (`iris.vrm`) でVTuber配信が完全動作するため、Live2Dは**非優先**とする。

### VRM (正式採用)
- `frontend/public/models/vrm/iris.vrm` で動作確認済み
- aituber-kit のVRMビューア（Three.js + @pixiv/three-vrm）で表示
- AivisSpeech でリップシンク対応
- YouTube Live 配信パイプライン構築済み

### Live2D (非優先・将来検討)
- `.cmo3` ファイルの状態：**パーツ分けが未完了**
- 完成に必要な手動作業：推定 **2-4週間**（パーツ分け + モデリング + 動作調整）
- VRM路線で十分な品質が確保できているため、当面は着手しない
- 将来的にLive2Dの方が表現力で優位な場面が出てきた場合に再検討

---

## Live2D化に必要な作業（参考）

### 現状の課題
- 画像解像度: 896×1344 → 4000px以上に拡大必要
- 背景透過: なし → 除去必要
- パーツ分け: なし → Live2D用に分離必要

### 必要なパーツ一覧

#### 顔パーツ
- [ ] 顔ベース（肌）
- [ ] 左目（白目・瞳・ハイライト・まつげ）
- [ ] 右目（白目・瞳・ハイライト・まつげ）
- [ ] 左眉毛
- [ ] 右眉毛
- [ ] 鼻
- [ ] 口（閉じ・半開き・開き）
- [ ] 歯
- [ ] 舌
- [ ] 頬（赤らみ用）

#### 髪パーツ
- [ ] 前髪
- [ ] 横髪（左）
- [ ] 横髪（右）
- [ ] 後ろ髪
- [ ] アホ毛（あれば）

#### 体パーツ
- [ ] 首
- [ ] 体（白衣）
- [ ] 左腕
- [ ] 右腕
- [ ] 左手
- [ ] 右手
- [ ] 光る球体（アクセサリー）

### 推奨ツール

#### Step 1: 高解像度化
- **Upscayl** (無料・オフライン): https://upscayl.org/
- **Real-ESRGAN** (無料): https://replicate.com/nightmareai/real-esrgan

#### Step 2: 背景除去
- **remove.bg** (無料枠あり): https://www.remove.bg/
- **Rembg** (無料・ローカル): pip install rembg

#### Step 3: パーツ分け
- **komiko.ai** (無料): https://komiko.app/
- **Live2D素材分けプラグイン** (Photoshop用)

#### Step 4: 不足パーツ生成
- **Midjourney** / **Stable Diffusion**
- **ChatGPT DALL-E** (キャラ一貫性のため)

#### Step 5: モデリング
- **Live2D Cubism** (42日無料): https://www.live2d.com/

#### Step 6: 動作確認
- **VTube Studio** (無料): Steam

### 参考リンク
- Live2D公式チュートリアル: https://docs.live2d.com/
- パーツ分けガイド: https://saraemi.com/vtuber/2022/01/13/live2d_psd/
