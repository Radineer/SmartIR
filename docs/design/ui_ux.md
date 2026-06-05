# UI/UX設計書

## 1. デザインシステム

### 1.1 カラーパレット
```css
:root {
  /* プライマリーカラー */
  --primary-100: #E3F2FD;  /* 最も薄い */
  --primary-500: #2196F3;  /* 基本 */
  --primary-900: #0D47A1;  /* 最も濃い */

  /* セカンダリーカラー */
  --secondary-100: #FFF8E1;
  --secondary-500: #FFC107;
  --secondary-900: #FF6F00;

  /* グレースケール */
  --gray-100: #F5F5F5;
  --gray-300: #E0E0E0;
  --gray-500: #9E9E9E;
  --gray-700: #616161;
  --gray-900: #212121;

  /* システムカラー */
  --success: #4CAF50;
  --warning: #FF9800;
  --error: #F44336;
  --info: #2196F3;
}
```

### 1.2 タイポグラフィ
```css
:root {
  /* 日本語フォント */
  --font-jp: 'Noto Sans JP', sans-serif;
  
  /* 英数字フォント */
  --font-en: 'Roboto', sans-serif;
  
  /* フォントサイズ */
  --text-xs: 0.75rem;   /* 12px */
  --text-sm: 0.875rem;  /* 14px */
  --text-base: 1rem;    /* 16px */
  --text-lg: 1.125rem;  /* 18px */
  --text-xl: 1.25rem;   /* 20px */
  --text-2xl: 1.5rem;   /* 24px */
  --text-3xl: 1.875rem; /* 30px */
}
```

### 1.3 コンポーネント
```typescript
// ボタンコンポーネント
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'outline';
  size: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}

// カードコンポーネント
interface CardProps {
  title: string;
  description: string;
  image?: string;
  tags?: string[];
  onClick?: () => void;
}
```

## 2. 画面設計

### 2.1 トップページ
```
┌────────────────────────────────────────────┐
│ ヘッダー                                    │
├────────────────────────────────────────────┤
│ メインビジュアル                            │
│ ┌──────────────────────────────────────┐   │
│ │ サービス説明                         │   │
│ │ CTAボタン                           │   │
│ └──────────────────────────────────────┘   │
├────────────────────────────────────────────┤
│ 新着レポート                                │
│ ┌────────┐ ┌────────┐ ┌────────┐          │
│ │カード1 │ │カード2 │ │カード3 │          │
│ └────────┘ └────────┘ └────────┘          │
├────────────────────────────────────────────┤
│ AIVtuber配信スケジュール                    │
│ ┌─────────────────────┐                    │
│ │カレンダー表示      │                    │
│ └─────────────────────┘                    │
└────────────────────────────────────────────┘
```

### 2.2 ダッシュボード
```
┌────────────────────────────────────────────┐
│ ヘッダー：ロゴ | 検索バー | ユーザーメニュー │
├────────┬───────────────────────────────────┤
│        │ メインコンテンツ                  │
│サイド  │ ┌────────────────────────────┐    │
│バー    │ │フィルター/ソート            │    │
│        │ ├────────────────────────────┤    │
│企業    │ │レポートリスト              │    │
│セク    │ │ ┌──────┐ ┌──────┐ ┌──────┐│    │
│ター    │ │ │Card1 │ │Card2 │ │Card3 ││    │
│        │ │ └──────┘ └──────┘ └──────┘│    │
│お気に  │ └────────────────────────────┘    │
│入り    │                                   │
└────────┴───────────────────────────────────┘
```

### 2.3 レポート詳細
```
┌────────────────────────────────────────────┐
│ ヘッダー                                    │
├────────────────────────────────────────────┤
│ 企業情報ヘッダー                            │
│ [企業名] [証券コード] [業種]                │
├────┬───────────────────────────────────────┤
│    │ レポート本文                          │
│サイ│ ┌────────────────────────────────┐    │
│ド │ │要約                            │    │
│メニ│ ├────────────────────────────────┤    │
│ュー│ │重要ポイント                    │    │
│    │ ├────────────────────────────────┤    │
│PDF │ │詳細分析                        │    │
│DL  │ └────────────────────────────────┘    │
└────┴───────────────────────────────────────┘
```

## 3. インタラクション設計

### 3.1 アニメーション
```typescript
// フェードイン
const fadeIn = keyframes`
  from { opacity: 0; }
  to { opacity: 1; }
`;

// スライドイン
const slideIn = keyframes`
  from { transform: translateX(-100%); }
  to { transform: translateX(0); }
`;
```

### 3.2 ホバーエフェクト
```css
.card {
  transition: transform 0.2s ease-in-out;
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
```

### 3.3 ローディング状態
```typescript
interface LoadingState {
  isLoading: boolean;
  progress?: number;  // 0-100
  message?: string;
}

const LoadingSpinner = ({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) => {
  // スピナーの実装
};
```

## 4. レスポンシブデザイン

### 4.1 ブレークポイント
```css
:root {
  --breakpoint-sm: 640px;   /* スマートフォン */
  --breakpoint-md: 768px;   /* タブレット */
  --breakpoint-lg: 1024px;  /* 小型デスクトップ */
  --breakpoint-xl: 1280px;  /* 大型デスクトップ */
}
```

### 4.2 レイアウトグリッド
```css
.grid-container {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 1rem;
}

@media (max-width: 768px) {
  .grid-container {
    grid-template-columns: repeat(4, 1fr);
  }
}
```

## 5. アクセシビリティ

### 5.1 WAI-ARIA対応
```typescript
// アクセシブルなボタン
const Button = ({ label, onClick }: ButtonProps) => (
  <button
    role="button"
    aria-label={label}
    onClick={onClick}
  >
    {label}
  </button>
);

// アクセシブルなモーダル
const Modal = ({ isOpen, title, children }: ModalProps) => (
  <div
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
  >
    <h2 id="modal-title">{title}</h2>
    {children}
  </div>
);
```

### 5.2 キーボードナビゲーション
```typescript
const handleKeyPress = (e: KeyboardEvent) => {
  if (e.key === 'Enter' || e.key === ' ') {
    // アクション実行
  }
};
```

## 6. エラー・フィードバック

### 6.1 エラー表示
```typescript
interface ErrorState {
  type: 'error' | 'warning' | 'info';
  message: string;
  action?: () => void;
}

const ErrorMessage = ({ type, message }: ErrorState) => (
  <div role="alert" className={`alert alert-${type}`}>
    {message}
  </div>
);
```

### 6.2 フィードバックUI
```typescript
interface ToastProps {
  message: string;
  type: 'success' | 'error' | 'info';
  duration?: number;
}

const Toast = ({ message, type, duration = 3000 }: ToastProps) => {
  // トースト通知の実装
};
```

## 7. パフォーマンス最適化

### 7.1 画像最適化
```typescript
interface OptimizedImageProps {
  src: string;
  alt: string;
  sizes: {
    sm: string;
    md: string;
    lg: string;
  };
}

const OptimizedImage = ({ src, alt, sizes }: OptimizedImageProps) => (
  <picture>
    <source media="(min-width: 1024px)" srcSet={sizes.lg} />
    <source media="(min-width: 768px)" srcSet={sizes.md} />
    <img src={sizes.sm} alt={alt} loading="lazy" />
  </picture>
);
```

### 7.2 コンポーネントの遅延ロード
```typescript
const LazyLoadedChart = React.lazy(() => import('./Chart'));

const ChartContainer = () => (
  <Suspense fallback={<LoadingSpinner />}>
    <LazyLoadedChart />
  </Suspense>
);
```

## 8. AIVtuber配信UI

### 8.1 配信画面レイアウト
```
┌────────────────────────────────────────────┐
│ メイン画面                                  │
│ ┌────────────────────┐ ┌────────────────┐  │
│ │                    │ │企業情報        │  │
│ │  VTuber表示エリア  │ │チャート表示    │  │
│ │                    │ │重要ポイント    │  │
│ └────────────────────┘ └────────────────┘  │
├────────────────────────────────────────────┤
│ チャット/コメントエリア                     │
│ ┌────────────────────────────────────────┐ │
│ │                                        │ │
│ └────────────────────────────────────────┘ │
└────────────────────────────────────────────┘
```

### 8.2 配信コントロール
```typescript
interface StreamControlProps {
  isLive: boolean;
  viewerCount: number;
  startTime: Date;
  onToggleLive: () => void;
}

const StreamControl = (props: StreamControlProps) => {
  // 配信コントロールUIの実装
};
```

## 9. アナリティクス設計

### 9.1 トラッキングイベント
```typescript
interface TrackingEvent {
  category: 'page_view' | 'interaction' | 'conversion';
  action: string;
  label?: string;
  value?: number;
}

const trackEvent = (event: TrackingEvent) => {
  // Google Analyticsなどへの送信
};
```

### 9.2 ヒートマップ
```typescript
interface HeatmapConfig {
  element: HTMLElement;
  clicks: boolean;
  scroll: boolean;
  movement: boolean;
}

const initHeatmap = (config: HeatmapConfig) => {
  // Hotjarなどの設定
};
``` 