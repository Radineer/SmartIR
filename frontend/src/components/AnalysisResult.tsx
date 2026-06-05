import type { AnalysisResult as AnalysisResultType } from "@/types";

interface AnalysisResultProps {
  result: AnalysisResultType;
}

export default function AnalysisResult({ result }: AnalysisResultProps) {
  const { sentiment } = result;

  return (
    <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
      {/* センチメント */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">センチメント分析</h3>
        <div className="flex space-x-4">
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-green-600">ポジティブ</span>
              <span>{(sentiment.positive * 100).toFixed(0)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full"
                style={{ width: `${sentiment.positive * 100}%` }}
              />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-red-600">ネガティブ</span>
              <span>{(sentiment.negative * 100).toFixed(0)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-red-500 h-2 rounded-full"
                style={{ width: `${sentiment.negative * 100}%` }}
              />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-600">ニュートラル</span>
              <span>{(sentiment.neutral * 100).toFixed(0)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-gray-400 h-2 rounded-full"
                style={{ width: `${sentiment.neutral * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 重要ポイント */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">重要ポイント</h3>
        <ul className="space-y-2">
          {result.key_points.map((point, index) => (
            <li key={index} className="flex items-start">
              <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs mr-2">
                {index + 1}
              </span>
              <span className="text-sm text-gray-700">{point.replace(/^\d+\.\s*/, "")}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* 要約 */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">要約</h3>
        <p className="text-sm text-gray-600 whitespace-pre-wrap">{result.summary}</p>
      </div>

      {result.processing_time && (
        <p className="text-xs text-gray-400">処理時間: {result.processing_time}秒</p>
      )}
    </div>
  );
}
