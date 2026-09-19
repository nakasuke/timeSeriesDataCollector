# データ収集・メタデータ管理システム Web API外部仕様書

| 項目 | 内容 |
|---|---|
| 文書版 | 0.1（ドラフト） |
| 作成日 | 2026-09-18 |
| ベースパス | `/api/v1` |
| データ形式 | JSON（UTF-8） |

## 1. API方針

- 外部インターフェースはRESTを採用する。
- Graph DBの構造やGremlinクエリは外部へ公開しない。
- 日時はRFC 3339形式のUTCで送受信する。例：`2026-09-18T03:00:00Z`。
- IDは文字列として扱い、大文字・小文字を区別する。
- 更新系APIは監査対象とする。
- 大量データ取得はページングまたはストリーミング方式へ拡張できる設計とする。

## 2. 利用者区分

| API利用者 | 主な操作 |
|---|---|
| 表示アプリ | 信号検索、表示可能範囲取得、時系列データ取得 |
| データ収集アプリ（Collector） | 登録、heartbeat、収集能力・取得可能範囲同期、収集結果送信 |
| 運用管理者 | アプリ・信号関係設定、Collector確認、ジョブ確認・再試行・取消 |
| 収集スケジューラ | Collectorへの収集要求（要求先API） |

## 3. 共通仕様

### 3.1 HTTPヘッダー

| ヘッダー | 必須 | 説明 |
|---|---|---|
| `Authorization: Bearer <token>` | ○ | 認証トークン |
| `Content-Type: application/json` | JSON本文時○ | リクエスト形式 |
| `Accept: application/json` | 推奨 | 応答形式 |
| `X-Request-Id` | 任意 | 呼出元で生成する追跡ID。未指定時はサーバが生成 |
| `Idempotency-Key` | 条件付き | 登録・ジョブ受付・結果送信など再送可能なPOSTで使用 |

### 3.2 共通エラーレスポンス

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "signal_ids must contain at least one item",
    "details": [
      { "field": "signal_ids", "reason": "min_items" }
    ],
    "request_id": "req-01K5..."
  }
}
```

| HTTP | 用途 |
|---|---|
| `400` | JSON形式不正、必須項目不足、値域不正 |
| `401` | 未認証 |
| `403` | 権限不足 |
| `404` | 対象リソースなし |
| `409` | 状態競合、未計算、同一IDの内容不一致 |
| `413` | 要求件数または本文サイズ超過 |
| `422` | 形式は正しいが業務上処理不能 |
| `429` | レート制限超過 |
| `500` | サーバ内部エラー |
| `503` | 依存サービス停止、一時利用不可 |

### 3.3 ページング

一覧APIはカーソル方式を使用する。

- `limit`: 1～1000、既定100
- `cursor`: 前回応答の`next_cursor`
- 応答：`items`、`next_cursor`。続きがなければ`next_cursor`は`null`

## 4. 表示アプリ向けAPI

### 4.1 信号一覧取得

`GET /api/v1/signals`

#### クエリ

| 名前 | 必須 | 説明 |
|---|---|---|
| `application_id` | 任意 | 当該アプリが利用する信号に限定 |
| `plant_id` | 任意 | Plantに属する信号に限定 |
| `equipment_id` | 任意 | Equipmentに属する信号に限定 |
| `q` | 任意 | ID・名称の部分一致 |
| `limit`, `cursor` | 任意 | ページング |

#### `200 OK`

```json
{
  "items": [
    {
      "signal_id": "TIC101.PV",
      "name": "温度指示調節計101 PV",
      "signal_type": "AI",
      "unit": "degC",
      "expected_interval_sec": 60,
      "plant_id": "plant-1",
      "equipment_id": "eq-p101",
      "storage": { "database_id": "history-db", "table_name": "ai_mhr" }
    }
  ],
  "next_cursor": null
}
```

### 4.2 表示可能範囲取得

`POST /api/v1/available-range`

指定した全信号について、欠測なく同時に表示できる共通有効範囲を返す。元の時系列テーブルは走査せず、事前計算済み区間を使用する。

#### リクエスト

```json
{
  "signal_ids": ["TIC101.PV", "FIC202.PV", "PV_MODE_01"],
  "range_hint": {
    "start_time": "2025-01-01T00:00:00Z",
    "end_time": "2025-12-31T23:59:00Z"
  },
  "allow_partial": false
}
```

| フィールド | 型 | 必須 | 制約・説明 |
|---|---|---|---|
| `signal_ids` | string[] | ○ | 1～1000件、重複不可 |
| `range_hint` | object | 任意 | 計算結果を指定期間へ限定。収集要求ではない |
| `range_hint.start_time` | datetime | 条件付き | end_timeより前 |
| `range_hint.end_time` | datetime | 条件付き | start_timeより後 |
| `allow_partial` | boolean | 任意 | 既定false。未準備信号を除外して計算する場合のみtrue |

#### `200 OK`

```json
{
  "common_valid_periods": [
    {
      "start_time": "2025-01-01T00:00:00Z",
      "end_time": "2025-03-31T23:59:00Z"
    },
    {
      "start_time": "2025-11-01T00:00:00Z",
      "end_time": "2025-12-31T23:59:00Z"
    }
  ],
  "signals": [
    { "signal_id": "TIC101.PV", "table_name": "ai_mhr", "status": "READY", "availability_updated_at": "2026-09-18T02:55:00Z" },
    { "signal_id": "FIC202.PV", "table_name": "ai_mhr", "status": "READY", "availability_updated_at": "2026-09-18T02:55:00Z" },
    { "signal_id": "PV_MODE_01", "table_name": "do_mhr", "status": "READY", "availability_updated_at": "2026-09-18T02:55:00Z" }
  ],
  "partial": false,
  "warnings": [],
  "request_id": "req-01K5..."
}
```

`signals[].status`：

| 値 | 意味 |
|---|---|
| `READY` | 保存先解決済み、有効区間計算済み |
| `SIGNAL_NOT_FOUND` | 信号マスタに存在しない |
| `STORAGE_NOT_RESOLVED` | 保存先テーブル未解決 |
| `AVAILABILITY_NOT_COMPUTED` | 有効区間未計算 |
| `DISABLED` | 信号が無効化されている |

- `allow_partial=false`で`READY`以外を含む場合は`409 RANGE_NOT_READY`とする。
- `allow_partial=true`の場合は`READY`の信号だけで計算し、`partial=true`と除外理由を返す。
- 全信号が`READY`でも積集合がなければ、正常応答で`common_valid_periods: []`を返す。

### 4.3 時系列データ取得

`POST /api/v1/data/query`

#### リクエスト

```json
{
  "signal_ids": ["TIC101.PV", "FIC202.PV"],
  "start_time": "2025-03-01T00:00:00Z",
  "end_time": "2025-03-01T01:00:00Z",
  "format": "series",
  "include_quality": true
}
```

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `signal_ids` | string[] | ○ | 対象信号 |
| `start_time` | datetime | ○ | 開始、包含 |
| `end_time` | datetime | ○ | 終了、包含 |
| `format` | string | 任意 | 初期版は`series`のみ |
| `include_quality` | boolean | 任意 | 既定true |

#### `200 OK`

```json
{
  "series": [
    {
      "signal_id": "TIC101.PV",
      "points": [
        { "date_time": "2025-03-01T00:00:00Z", "value": 123.4, "quality": "GOOD" },
        { "date_time": "2025-03-01T00:01:00Z", "value": 123.5, "quality": "GOOD" }
      ]
    }
  ],
  "request_id": "req-01K5..."
}
```

応答上限を超える場合は`413 QUERY_TOO_LARGE`を返し、期間分割または将来の非同期エクスポートAPIを案内する。

## 5. Collector向けAPI（本システムが提供）

### 5.1 Collector登録

`POST /api/v1/collectors`

管理者権限または事前登録トークンを必要とする。

```json
{
  "collector_id": "collector-a",
  "name": "第1工場収集アプリ",
  "plant_ids": ["plant-1"],
  "endpoint": "https://collector-a.example.local/api/v1",
  "protocol_version": "1.0"
}
```

#### `201 Created`

```json
{
  "collector_id": "collector-a",
  "status": "REGISTERED",
  "created_at": "2026-09-18T03:00:00Z"
}
```

同じ`collector_id`と同じ内容の冪等再送は既存結果を返す。内容が異なる場合は`409 COLLECTOR_ID_CONFLICT`とする。

### 5.2 Heartbeat

`POST /api/v1/collectors/{collector_id}/heartbeat`

```json
{
  "sent_at": "2026-09-18T03:05:00Z",
  "application_version": "2.1.0",
  "health": "HEALTHY",
  "active_jobs": 2,
  "queue_capacity": 8
}
```

成功時は`204 No Content`。サーバ時刻との差が許容値を超えた場合は`200`でwarningを返してもよい。

### 5.3 収集能力同期

`PUT /api/v1/collectors/{collector_id}/capabilities`

このCollectorが収集可能な信号の全量スナップショットを登録する。

```json
{
  "revision": "2026-09-18T03:00:00Z",
  "signals": [
    {
      "signal_id": "TIC101.PV",
      "source_identifier": "AI:TIC101.PV",
      "expected_interval_sec": 60,
      "priority": 1
    }
  ]
}
```

#### `200 OK`

```json
{
  "collector_id": "collector-a",
  "revision": "2026-09-18T03:00:00Z",
  "accepted": 1,
  "rejected": []
}
```

古い`revision`による上書きは`409 STALE_REVISION`とする。

### 5.4 収集元取得可能範囲同期

`PUT /api/v1/collectors/{collector_id}/source-availability`

```json
{
  "observed_at": "2026-09-18T03:00:00Z",
  "signals": [
    {
      "signal_id": "TIC101.PV",
      "periods": [
        { "start_time": "2025-01-01T00:00:00Z", "end_time": "2026-09-18T02:59:00Z" }
      ]
    }
  ]
}
```

- 全量置換か差分更新かを曖昧にしないため、初期版はCollector単位の全量スナップショットとする。
- 本APIの期間は「プラントから取得可能」であり、「本システムに保存済み」や「欠測なし」を意味しない。

### 5.5 収集結果送信

`POST /api/v1/collection-jobs/{job_id}/results`

`Idempotency-Key`を必須とする。大容量時はチャンクごとに送信する。

```json
{
  "chunk_id": "000001",
  "final_chunk": true,
  "items": [
    {
      "signal_id": "TIC101.PV",
      "requested_start": "2026-09-18T00:00:00Z",
      "requested_end": "2026-09-18T00:59:00Z",
      "result": "SUCCESS",
      "points": [
        { "date_time": "2026-09-18T00:00:00Z", "value": 120.1, "quality": "GOOD" }
      ]
    }
  ]
}
```

#### `202 Accepted`

```json
{
  "job_id": "job-01K5...",
  "chunk_id": "000001",
  "status": "ACCEPTED",
  "received_at": "2026-09-18T03:10:00Z"
}
```

`result`は`SUCCESS`、`NO_DATA`、`PARTIAL`、`FAILED`。`NO_DATA`は正常に問い合わせたが元データが存在しなかったことを示す。`FAILED`では`points`を空とし、`error`を付ける。

## 6. ジョブ参照・運用API

### 6.1 ジョブ状態取得

`GET /api/v1/collection-jobs/{job_id}`

```json
{
  "job_id": "job-01K5...",
  "collector_id": "collector-a",
  "status": "RUNNING",
  "priority": 50,
  "created_at": "2026-09-18T03:00:00Z",
  "started_at": "2026-09-18T03:00:03Z",
  "completed_at": null,
  "items": [
    {
      "signal_id": "TIC101.PV",
      "requested_start": "2026-09-18T00:00:00Z",
      "requested_end": "2026-09-18T00:59:00Z",
      "status": "RUNNING"
    }
  ],
  "retry_count": 0
}
```

### 6.2 ジョブ一覧取得

`GET /api/v1/collection-jobs?collector_id=collector-a&status=FAILED&limit=100`

共通ページング仕様を使用する。管理者は期間、信号、状態でも絞り込める。

### 6.3 ジョブ再試行

`POST /api/v1/collection-jobs/{job_id}/retry`

失敗または部分成功ジョブの未完了範囲から新しいジョブを作る。元ジョブを上書きしない。

#### `202 Accepted`

```json
{
  "original_job_id": "job-01K5-old",
  "new_job_id": "job-01K5-new",
  "status": "QUEUED"
}
```

### 6.4 ジョブ取消

`POST /api/v1/collection-jobs/{job_id}/cancel`

`QUEUED`、`DISPATCHED`、`RUNNING`が対象。Collector側の取消可否により、`RUNNING`では取消要求中となる場合がある。

## 7. アプリ・信号関係管理API

### 7.1 アプリの利用信号更新

`PUT /api/v1/applications/{application_id}/signals`

全量置換として定義する。変更により必要範囲の再評価を起動する。

```json
{
  "revision": 4,
  "signal_ids": ["TIC101.PV", "FIC202.PV"],
  "required_range": {
    "mode": "FROM_DATE_TO_NOW",
    "start_time": "2025-01-01T00:00:00Z"
  }
}
```

更新成功時は新しい`revision`を返す。競合時は`409 REVISION_CONFLICT`とする。

## 8. 本システムからCollectorへ要求するAPI

以下はCollector側が提供する契約であり、本システムの受信APIではない。Collectorがポーリング方式を採る場合は別途キュー取得APIに置き換える。

### 8.1 収集要求

`POST {collector.endpoint}/collection-jobs`

```json
{
  "job_id": "job-01K5...",
  "callback_url": "https://data-platform.example/api/v1/collection-jobs/job-01K5.../results",
  "priority": 50,
  "items": [
    {
      "signal_id": "TIC101.PV",
      "source_identifier": "AI:TIC101.PV",
      "start_time": "2026-09-18T00:00:00Z",
      "end_time": "2026-09-18T00:59:00Z"
    }
  ]
}
```

#### `202 Accepted`

```json
{
  "job_id": "job-01K5...",
  "status": "ACCEPTED"
}
```

同じ`job_id`の再送は冪等に扱う。内容が異なる場合は`409 JOB_ID_CONFLICT`とする。

### 8.2 取消要求

`POST {collector.endpoint}/collection-jobs/{job_id}/cancel`

Collectorは取消受付結果として`202`、既に完了している場合は現在状態を含む`409`を返す。

## 9. 認証・認可

- 方式はOAuth 2.0 Client Credentialsまたは同等のサービス間認証を候補とし、最終決定は別途行う。
- スコープ例：`signals:read`、`data:read`、`collector:write`、`jobs:read`、`jobs:manage`、`metadata:write`。
- Collectorトークンは自身の`collector_id`および担当Plant／Signalに限定する。
- ブラウザからの直接利用がある場合、許可Originを限定し、管理APIはCORS対象外とする。

## 10. レート・サイズ制限（初期値）

| 対象 | 初期値 |
|---|---|
| `available-range` | 1要求1000信号まで |
| `data/query` | 1要求100信号、最大100万点相当まで |
| capability同期 | 1要求1万信号まで。超過時は分割方式を追加 |
| result送信 | 1本文50 MiB以下、1チャンク10万点まで |
| heartbeat | Collectorごとに最短10秒間隔 |

制限値は負荷試験後に確定する。超過時は`413`または`429`を返す。

## 11. バージョニングと互換性

- メジャーバージョンはURLの`/v1`で表す。
- 後方互換のフィールド追加は同一バージョンで行う。クライアントは未知フィールドを無視する。
- 必須項目の追加、型変更、意味変更、エンドポイント削除は新メジャーバージョンとする。
- 廃止予定はレスポンスヘッダーと運用通知で予告する。

## 12. API一覧

| Method | Path | 利用者 | 概要 |
|---|---|---|---|
| GET | `/signals` | 表示アプリ | 信号一覧 |
| POST | `/available-range` | 表示アプリ | 共通表示可能範囲 |
| POST | `/data/query` | 表示アプリ | 時系列データ取得 |
| POST | `/collectors` | 管理者／Collector | Collector登録 |
| POST | `/collectors/{id}/heartbeat` | Collector | 稼働通知 |
| PUT | `/collectors/{id}/capabilities` | Collector | 収集能力同期 |
| PUT | `/collectors/{id}/source-availability` | Collector | 取得可能範囲同期 |
| POST | `/collection-jobs/{id}/results` | Collector | 収集結果送信 |
| GET | `/collection-jobs/{id}` | 管理者 | ジョブ状態 |
| GET | `/collection-jobs` | 管理者 | ジョブ一覧 |
| POST | `/collection-jobs/{id}/retry` | 管理者 | 再試行 |
| POST | `/collection-jobs/{id}/cancel` | 管理者 | 取消 |
| PUT | `/applications/{id}/signals` | 管理者 | 利用信号設定 |

## 13. 未決事項

- Collector連携をpush（本書8章）にするか、Collectorからのpollにするか
- データ照会の同期応答上限と非同期エクスポートAPIの要否
- 時系列値の型を数値に限定するか、boolean／stringを共通表現に含めるか
- `quality`コード体系
- 認証方式、トークン有効期限、証明書運用
- APIの具体的なレート制限値
- OpenAPI 3.1定義ファイルの作成時期

